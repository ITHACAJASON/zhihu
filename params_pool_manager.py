#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
反爬虫参数池管理器

管理动态提取的反爬虫参数，包括存储、轮换、验证和自动更新
"""

import json
import time
import sqlite3
import threading
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from loguru import logger
import random
from contextlib import contextmanager


@dataclass
class ParamsRecord:
    """参数记录"""
    id: Optional[int] = None
    x_zse_96: str = ""
    x_zst_81: str = ""
    x_zse_93: str = ""
    x_xsrftoken: str = ""
    x_zse_83: str = ""
    x_du_bid: str = ""
    session_id: str = ""
    user_agent: str = ""
    referer: str = ""
    question_id: str = ""
    created_at: float = 0.0
    last_used_at: float = 0.0
    use_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    is_active: bool = True
    
    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()
        if self.last_used_at == 0.0:
            self.last_used_at = self.created_at
            
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.use_count == 0:
            return 1.0
        return self.success_count / self.use_count
        
    @property
    def age_minutes(self) -> float:
        """参数年龄（分钟）"""
        return (time.time() - self.created_at) / 60
        
    @property
    def is_expired(self) -> bool:
        """是否已过期（超过1小时）"""
        return self.age_minutes > 60
        
    def to_headers(self) -> Dict[str, str]:
        """转换为请求头格式"""
        headers = {
            'x-zse-96': self.x_zse_96,
            'x-zst-81': self.x_zst_81,
            'user-agent': self.user_agent,
            'referer': self.referer
        }
        
        # 添加可选的请求头（如果存在）
        if self.x_zse_93:
            headers['x-zse-93'] = self.x_zse_93
        if self.x_xsrftoken:
            headers['x-xsrftoken'] = self.x_xsrftoken
        if self.x_zse_83:
            headers['x-zse-83'] = self.x_zse_83
        if self.x_du_bid:
            headers['x-du-bid'] = self.x_du_bid
            
        return headers


class ParamsPoolManager:
    """参数池管理器"""
    
    def __init__(self, db_path: str = "params_pool.db", max_pool_size: int = 100):
        """
        初始化参数池管理器
        
        Args:
            db_path: 数据库文件路径
            max_pool_size: 参数池最大容量
        """
        self.db_path = Path(db_path)
        self.max_pool_size = max_pool_size
        self._lock = threading.RLock()
        self._init_database()
        
    def _init_database(self):
        """初始化数据库"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS params_pool (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    x_zse_96 TEXT NOT NULL,
                    x_zst_81 TEXT NOT NULL,
                    x_zse_93 TEXT DEFAULT '',
                    x_xsrftoken TEXT DEFAULT '',
                    x_zse_83 TEXT DEFAULT '',
                    x_du_bid TEXT DEFAULT '',
                    session_id TEXT NOT NULL,
                    user_agent TEXT NOT NULL,
                    referer TEXT NOT NULL,
                    question_id TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    last_used_at REAL NOT NULL,
                    use_count INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1,
                    UNIQUE(x_zse_96, x_zst_81, session_id)
                )
            """)
            
            # 添加新字段（如果表已存在）
            try:
                conn.execute("ALTER TABLE params_pool ADD COLUMN x_zse_93 TEXT DEFAULT ''")
            except:
                pass
            try:
                conn.execute("ALTER TABLE params_pool ADD COLUMN x_xsrftoken TEXT DEFAULT ''")
            except:
                pass
            try:
                conn.execute("ALTER TABLE params_pool ADD COLUMN x_zse_83 TEXT DEFAULT ''")
            except:
                pass
            try:
                conn.execute("ALTER TABLE params_pool ADD COLUMN x_du_bid TEXT DEFAULT ''")
            except:
                pass
            
            # 创建索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON params_pool(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_is_active ON params_pool(is_active)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_success_rate ON params_pool(success_count, use_count)")
            
            conn.commit()
            
    @contextmanager
    def _get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
            
    def add_params(self, params: Dict) -> bool:
        """
        添加参数到池中
        
        Args:
            params: 参数字典
            
        Returns:
            是否添加成功
        """
        try:
            record = ParamsRecord(
                x_zse_96=params.get('x_zse_96', ''),
                x_zst_81=params.get('x_zst_81', ''),
                x_zse_93=params.get('x_zse_93', ''),
                x_xsrftoken=params.get('x_xsrftoken', ''),
                x_zse_83=params.get('x_zse_83', ''),
                x_du_bid=params.get('x_du_bid', ''),
                session_id=params.get('session_id', ''),
                user_agent=params.get('user_agent', ''),
                referer=params.get('referer', ''),
                question_id=params.get('question_id', ''),
                created_at=params.get('timestamp', time.time())
            )
            
            with self._lock:
                with self._get_connection() as conn:
                    # 检查是否已存在
                    existing = conn.execute(
                        "SELECT id FROM params_pool WHERE x_zse_96=? AND x_zst_81=? AND session_id=?",
                        (record.x_zse_96, record.x_zst_81, record.session_id)
                    ).fetchone()
                    
                    if existing:
                        logger.debug("参数已存在，跳过添加")
                        return False
                        
                    # 检查池容量
                    count = conn.execute("SELECT COUNT(*) as count FROM params_pool WHERE is_active=1").fetchone()['count']
                    
                    if count >= self.max_pool_size:
                        # 删除最旧的参数
                        conn.execute(
                            "DELETE FROM params_pool WHERE id IN (SELECT id FROM params_pool WHERE is_active=1 ORDER BY created_at LIMIT 1)"
                        )
                        
                    # 插入新参数
                    conn.execute("""
                        INSERT INTO params_pool (
                            x_zse_96, x_zst_81, x_zse_93, x_xsrftoken, x_zse_83, x_du_bid,
                            session_id, user_agent, referer, question_id, created_at, last_used_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        record.x_zse_96, record.x_zst_81, record.x_zse_93, record.x_xsrftoken,
                        record.x_zse_83, record.x_du_bid, record.session_id, record.user_agent,
                        record.referer, record.question_id, record.created_at, record.last_used_at
                    ))
                    
                    conn.commit()
                    logger.info(f"✅ 参数已添加到池中，当前池大小: {count + 1}")
                    return True
                    
        except Exception as e:
            logger.error(f"❌ 添加参数失败: {e}")
            return False
            
    def get_best_params(self, exclude_ids: List[int] = None) -> Optional[ParamsRecord]:
        """
        获取最佳参数
        
        Args:
            exclude_ids: 要排除的参数ID列表
            
        Returns:
            最佳参数记录，无可用参数返回None
        """
        exclude_ids = exclude_ids or []
        
        with self._lock:
            with self._get_connection() as conn:
                # 构建排除条件
                exclude_condition = ""
                params = []
                
                if exclude_ids:
                    placeholders = ','.join('?' * len(exclude_ids))
                    exclude_condition = f" AND id NOT IN ({placeholders})"
                    params.extend(exclude_ids)
                    
                # 查询可用参数，按成功率和新鲜度排序
                query = f"""
                    SELECT * FROM params_pool 
                    WHERE is_active=1 AND (? - created_at) < 3600 {exclude_condition}
                    ORDER BY 
                        CASE WHEN use_count = 0 THEN 1.0 ELSE CAST(success_count AS FLOAT) / use_count END DESC,
                        created_at DESC
                    LIMIT 1
                """
                
                row = conn.execute(query, [time.time()] + params).fetchone()
                
                if row:
                    return self._row_to_record(row)
                    
                logger.warning("⚠️ 参数池中无可用参数")
                return None
                
    def mark_params_used(self, params_id: int, success: bool = True):
        """
        标记参数使用情况
        
        Args:
            params_id: 参数ID
            success: 是否使用成功
        """
        with self._lock:
            with self._get_connection() as conn:
                if success:
                    conn.execute("""
                        UPDATE params_pool 
                        SET use_count = use_count + 1, 
                            success_count = success_count + 1,
                            last_used_at = ?
                        WHERE id = ?
                    """, (time.time(), params_id))
                else:
                    conn.execute("""
                        UPDATE params_pool 
                        SET use_count = use_count + 1, 
                            failure_count = failure_count + 1,
                            last_used_at = ?
                        WHERE id = ?
                    """, (time.time(), params_id))
                    
                    # 如果失败次数过多，标记为不可用
                    row = conn.execute(
                        "SELECT use_count, failure_count FROM params_pool WHERE id = ?", 
                        (params_id,)
                    ).fetchone()
                    
                    if row and row['use_count'] >= 5 and row['failure_count'] / row['use_count'] > 0.8:
                        conn.execute(
                            "UPDATE params_pool SET is_active = 0 WHERE id = ?", 
                            (params_id,)
                        )
                        logger.warning(f"⚠️ 参数 {params_id} 失败率过高，已标记为不可用")
                        
                conn.commit()
                
    def cleanup_expired_params(self) -> int:
        """
        清理过期参数
        
        Returns:
            清理的参数数量
        """
        with self._lock:
            with self._get_connection() as conn:
                # 删除超过1小时的参数
                cutoff_time = time.time() - 3600
                
                result = conn.execute(
                    "DELETE FROM params_pool WHERE created_at < ?",
                    (cutoff_time,)
                )
                
                deleted_count = result.rowcount
                conn.commit()
                
                if deleted_count > 0:
                    logger.info(f"🧹 清理了 {deleted_count} 个过期参数")
                    
                return deleted_count
                
    def get_pool_stats(self) -> Dict:
        """
        获取参数池统计信息
        
        Returns:
            统计信息字典
        """
        with self._get_connection() as conn:
            stats = conn.execute("""
                SELECT 
                    COUNT(*) as total_count,
                    COUNT(CASE WHEN is_active=1 THEN 1 END) as active_count,
                    COUNT(CASE WHEN (? - created_at) < 3600 THEN 1 END) as fresh_count,
                    AVG(CASE WHEN use_count > 0 THEN CAST(success_count AS FLOAT) / use_count END) as avg_success_rate,
                    MIN(created_at) as oldest_created_at,
                    MAX(created_at) as newest_created_at
                FROM params_pool
            """, (time.time(),)).fetchone()
            
            return {
                'total_count': stats['total_count'],
                'active_count': stats['active_count'],
                'fresh_count': stats['fresh_count'],
                'avg_success_rate': stats['avg_success_rate'] or 0.0,
                'oldest_age_minutes': (time.time() - (stats['oldest_created_at'] or time.time())) / 60,
                'newest_age_minutes': (time.time() - (stats['newest_created_at'] or time.time())) / 60
            }
            
    def get_random_params(self, count: int = 1) -> List[ParamsRecord]:
        """
        随机获取参数
        
        Args:
            count: 获取数量
            
        Returns:
            参数记录列表
        """
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM params_pool 
                WHERE is_active=1 AND (? - created_at) < 3600
                ORDER BY RANDOM()
                LIMIT ?
            """, (time.time(), count)).fetchall()
            
            return [self._row_to_record(row) for row in rows]
            
    def _row_to_record(self, row) -> ParamsRecord:
        """将数据库行转换为参数记录"""
        # 获取新字段，如果不存在则使用默认值
        try:
            x_zse_93 = row['x_zse_93'] if 'x_zse_93' in row.keys() else ''
        except (KeyError, IndexError):
            x_zse_93 = ''
            
        try:
            x_xsrftoken = row['x_xsrftoken'] if 'x_xsrftoken' in row.keys() else ''
        except (KeyError, IndexError):
            x_xsrftoken = ''
            
        try:
            x_zse_83 = row['x_zse_83'] if 'x_zse_83' in row.keys() else ''
        except (KeyError, IndexError):
            x_zse_83 = ''
            
        try:
            x_du_bid = row['x_du_bid'] if 'x_du_bid' in row.keys() else ''
        except (KeyError, IndexError):
            x_du_bid = ''
        
        return ParamsRecord(
            id=row['id'],
            x_zse_96=row['x_zse_96'],
            x_zst_81=row['x_zst_81'],
            x_zse_93=x_zse_93,
            x_xsrftoken=x_xsrftoken,
            x_zse_83=x_zse_83,
            x_du_bid=x_du_bid,
            session_id=row['session_id'],
            user_agent=row['user_agent'],
            referer=row['referer'],
            question_id=row['question_id'],
            created_at=row['created_at'],
            last_used_at=row['last_used_at'],
            use_count=row['use_count'],
            success_count=row['success_count'],
            failure_count=row['failure_count'],
            is_active=bool(row['is_active'])
        )
        
    def export_params(self, file_path: str) -> bool:
        """
        导出参数到JSON文件
        
        Args:
            file_path: 导出文件路径
            
        Returns:
            是否导出成功
        """
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    "SELECT * FROM params_pool WHERE is_active=1 ORDER BY created_at DESC"
                ).fetchall()
                
                records = [dict(row) for row in rows]
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(records, f, indent=2, ensure_ascii=False)
                    
                logger.info(f"✅ 已导出 {len(records)} 个参数到 {file_path}")
                return True
                
        except Exception as e:
            logger.error(f"❌ 导出参数失败: {e}")
            return False
            
    def import_params(self, file_path: str) -> int:
        """
        从JSON文件导入参数
        
        Args:
            file_path: 导入文件路径
            
        Returns:
            导入的参数数量
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                records = json.load(f)
                
            imported_count = 0
            
            for record in records:
                if self.add_params(record):
                    imported_count += 1
                    
            logger.info(f"✅ 已导入 {imported_count}/{len(records)} 个参数")
            return imported_count
            
        except Exception as e:
            logger.error(f"❌ 导入参数失败: {e}")
            return 0