"""批量采集管理器 - 集成数据库查询、断点续传、反爬虫检测功能"""

import asyncio
import time
import json
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from concurrent.futures import ThreadPoolExecutor

from database_query_manager import DatabaseQueryManager, QueryFilter, BatchCrawlTask
from resume_manager import ResumeManager, AntiCrawlDetection, TaskStatus, CrawlProgress
from smart_crawler import SmartCrawler
from monitor_recovery import MonitorRecovery


@dataclass
class BatchCrawlConfig:
    """批量采集配置"""
    concurrent_limit: int = 5  # 并发限制
    batch_size: int = 10  # 每批处理的URL数量
    request_delay: float = 1.0  # 请求间隔（秒）
    max_retries: int = 3  # 最大重试次数
    timeout: int = 30  # 请求超时时间
    auto_pause_on_anti_crawl: bool = True  # 检测到反爬虫时自动暂停
    enable_monitoring: bool = True  # 启用监控
    save_progress_interval: int = 10  # 保存进度间隔（处理多少个URL后保存一次）


class BatchCrawlManager:
    """批量采集管理器"""
    
    def __init__(self, config: BatchCrawlConfig = None):
        self.config = config or BatchCrawlConfig()
        self.db_manager = DatabaseQueryManager()
        self.resume_manager = ResumeManager(self.db_manager)
        self.logger = logging.getLogger(__name__)
        
        # 采集相关组件
        self.smart_crawler: Optional[SmartCrawler] = None
        self.monitor: Optional[MonitorRecovery] = None
        
        # 运行状态
        self._running_tasks: Dict[str, bool] = {}
        self._task_stats: Dict[str, Dict[str, int]] = {}
        
    async def initialize_crawler(self, chrome_user_data_dir: str = None, headless: bool = False):
        """初始化爬虫组件"""
        try:
            # 初始化SmartCrawler，传递必要的参数
            self.smart_crawler = SmartCrawler(
                params_db_path="params_pool.db",
                max_pool_size=100,
                max_concurrent=self.config.concurrent_limit,
                user_data_dir=chrome_user_data_dir,
                headless=headless
            )
            
            if self.config.enable_monitoring:
                # 创建MonitorRecovery时传递params_manager，启用自动参数提取
                self.monitor = MonitorRecovery(
                    self.smart_crawler.params_manager,
                    auto_extract_params=True
                )
                self.monitor.start_monitoring()
            
            self.logger.info("批量采集管理器初始化完成")
            return True
        except Exception as e:
            self.logger.error(f"初始化爬虫组件失败: {e}")
            return False
    
    def create_batch_task(self, name: str, description: str, query_filter: QueryFilter) -> str:
        """创建批量采集任务"""
        try:
            task_id = self.resume_manager.create_batch_task_with_progress(
                name, description, query_filter
            )
            
            # 初始化任务统计
            self._task_stats[task_id] = {
                'total': 0,
                'completed': 0,
                'failed': 0,
                'pending': 0,
                'processing': 0
            }
            
            self.logger.info(f"创建批量任务: {task_id} - {name}")
            return task_id
        except Exception as e:
            self.logger.error(f"创建批量任务失败: {e}")
            raise
    
    async def start_batch_crawl(self, task_id: str, resume_from_checkpoint: bool = False) -> Dict[str, Any]:
        """开始批量采集"""
        if not self.smart_crawler:
            raise RuntimeError("爬虫组件未初始化，请先调用 initialize_crawler()")
        
        # 检查任务是否存在
        task = self.db_manager.get_batch_crawl_task(task_id)
        if not task:
            raise ValueError(f"任务 {task_id} 不存在")
        
        # 标记任务为运行状态
        self._running_tasks[task_id] = True
        self.db_manager.update_batch_crawl_task_status(task_id, TaskStatus.RUNNING.value)
        
        try:
            if resume_from_checkpoint:
                self.logger.info(f"从断点恢复任务: {task_id}")
                resume_info = self.resume_manager.get_task_resume_point(task_id)
                self.logger.info(f"任务恢复点信息: {resume_info}")
            
            # 开始采集循环
            result = await self._crawl_loop(task_id)
            
            # 更新最终状态
            if result['completed'] == result['total']:
                self.db_manager.update_batch_crawl_task_status(task_id, TaskStatus.COMPLETED.value)
            elif result['failed'] > 0:
                self.db_manager.update_batch_crawl_task_status(
                    task_id, TaskStatus.FAILED.value, 
                    error_message=f"部分URL采集失败: {result['failed']}/{result['total']}"
                )
            
            return result
            
        except Exception as e:
            self.logger.error(f"批量采集任务 {task_id} 执行失败: {e}")
            self.db_manager.update_batch_crawl_task_status(
                task_id, TaskStatus.FAILED.value, error_message=str(e)
            )
            raise
        finally:
            self._running_tasks[task_id] = False
    
    async def _crawl_loop(self, task_id: str) -> Dict[str, Any]:
        """采集循环"""
        total_processed = 0
        total_completed = 0
        total_failed = 0
        
        while self._running_tasks.get(task_id, False):
            # 获取下一批待处理的URL
            batch_progress = self.resume_manager.get_next_batch_to_process(
                task_id, self.config.batch_size
            )
            
            if not batch_progress:
                self.logger.info(f"任务 {task_id} 没有更多待处理的URL")
                break
            
            self.logger.info(f"开始处理批次: {len(batch_progress)} 个URL")
            
            # 处理当前批次
            batch_results = await self._process_batch(task_id, batch_progress)
            
            # 统计结果
            batch_completed = sum(1 for r in batch_results if r['status'] == 'completed')
            batch_failed = sum(1 for r in batch_results if r['status'] == 'failed')
            
            total_processed += len(batch_progress)
            total_completed += batch_completed
            total_failed += batch_failed
            
            # 更新任务统计
            self._update_task_stats(task_id, batch_completed, batch_failed)
            
            self.logger.info(
                f"批次处理完成: 成功 {batch_completed}, 失败 {batch_failed}, "
                f"总进度: {total_completed}/{total_processed}"
            )
            
            # 检查是否需要暂停（反爬虫检测）
            if self._should_pause_task(task_id, batch_results):
                self.logger.warning(f"检测到反爬虫机制，暂停任务 {task_id}")
                self.resume_manager.pause_task(task_id, "检测到反爬虫机制")
                break
            
            # 请求间隔
            if self.config.request_delay > 0:
                await asyncio.sleep(self.config.request_delay)
        
        return {
            'task_id': task_id,
            'total': total_processed,
            'completed': total_completed,
            'failed': total_failed,
            'success_rate': total_completed / max(total_processed, 1) * 100
        }
    
    async def _process_batch(self, task_id: str, batch_progress: List[CrawlProgress]) -> List[Dict[str, Any]]:
        """处理一批URL"""
        results = []
        semaphore = asyncio.Semaphore(self.config.concurrent_limit)
        
        async def process_single_url(progress: CrawlProgress):
            async with semaphore:
                return await self._process_single_url(task_id, progress)
        
        # 并发处理
        tasks = [process_single_url(progress) for progress in batch_progress]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                progress = batch_progress[i]
                error_result = {
                    'question_id': progress.question_id,
                    'question_url': progress.question_url,
                    'status': 'failed',
                    'error': str(result)
                }
                processed_results.append(error_result)
                
                # 更新进度状态
                self.resume_manager.update_progress_status(
                    task_id, progress.question_id, 'failed', str(result), increment_retry=True
                )
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _process_single_url(self, task_id: str, progress: CrawlProgress) -> Dict[str, Any]:
        """处理单个URL"""
        question_id = progress.question_id
        question_url = progress.question_url
        
        try:
            # 更新状态为处理中
            self.resume_manager.update_progress_status(task_id, question_id, 'processing')
            
            # 执行采集
            self.logger.debug(f"开始采集: {question_url}")
            
            # 这里调用实际的采集逻辑
            crawl_result = await self._crawl_question_url(question_url)
            
            if crawl_result['success']:
                # 采集成功
                self.resume_manager.update_progress_status(task_id, question_id, 'completed')
                
                return {
                    'question_id': question_id,
                    'question_url': question_url,
                    'status': 'completed',
                    'data': crawl_result['data']
                }
            else:
                # 采集失败，检查是否为反爬虫
                error_info = self.resume_manager.handle_crawl_error(
                    task_id, question_id,
                    crawl_result.get('response_status', 0),
                    crawl_result.get('response_content', ''),
                    crawl_result.get('response_headers', {})
                )
                
                if error_info['is_anti_crawl']:
                    # 反爬虫错误
                    self.resume_manager.update_progress_status(
                        task_id, question_id, 'failed', 
                        f"反爬虫检测: {error_info['detection'].detection_type.value}"
                    )
                else:
                    # 普通错误，可能重试
                    if self.resume_manager.should_retry(progress.retry_count):
                        self.resume_manager.update_progress_status(
                            task_id, question_id, 'pending', 
                            error_info['error_message'], increment_retry=True
                        )
                    else:
                        self.resume_manager.update_progress_status(
                            task_id, question_id, 'failed', error_info['error_message']
                        )
                
                return {
                    'question_id': question_id,
                    'question_url': question_url,
                    'status': 'failed',
                    'error': crawl_result.get('error', '未知错误'),
                    'is_anti_crawl': error_info.get('is_anti_crawl', False)
                }
                
        except Exception as e:
            self.logger.error(f"处理URL失败 {question_url}: {e}")
            self.resume_manager.update_progress_status(
                task_id, question_id, 'failed', str(e), increment_retry=True
            )
            
            return {
                'question_id': question_id,
                'question_url': question_url,
                'status': 'failed',
                'error': str(e)
            }
    
    async def _crawl_question_url(self, question_url: str) -> Dict[str, Any]:
        """采集单个问题URL（实际的采集逻辑）"""
        try:
            if not self.smart_crawler:
                raise RuntimeError("SmartCrawler 未初始化")
            
            # 从URL中提取question_id
            question_id = question_url.split('/')[-1]
            
            # 调用SmartCrawler的实际采集方法
            crawl_result = await self.smart_crawler.crawl_question_feeds(
                question_id=question_id,
                limit=20,
                offset=0
            )
            
            if crawl_result.success:
                return {
                    'success': True,
                    'data': crawl_result.data
                }
            else:
                return {
                    'success': False,
                    'error': crawl_result.error or '采集失败',
                    'response_status': 0,
                    'response_content': '',
                    'response_headers': {}
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'response_status': 0,
                'response_content': '',
                'response_headers': {}
            }
    
    def _should_pause_task(self, task_id: str, batch_results: List[Dict[str, Any]]) -> bool:
        """判断是否应该暂停任务"""
        if not self.config.auto_pause_on_anti_crawl:
            return False
        
        # 检查批次中反爬虫错误的比例
        anti_crawl_count = sum(1 for r in batch_results if r.get('is_anti_crawl', False))
        anti_crawl_ratio = anti_crawl_count / max(len(batch_results), 1)
        
        # 如果反爬虫错误超过50%，暂停任务
        return anti_crawl_ratio > 0.5
    
    def _update_task_stats(self, task_id: str, completed: int, failed: int):
        """更新任务统计"""
        if task_id not in self._task_stats:
            self._task_stats[task_id] = {
                'total': 0, 'completed': 0, 'failed': 0, 'pending': 0, 'processing': 0
            }
        
        stats = self._task_stats[task_id]
        stats['completed'] += completed
        stats['failed'] += failed
        
        # 更新数据库中的任务统计
        self.db_manager.update_batch_crawl_task_stats(
            task_id, completed_urls=stats['completed'], failed_urls=stats['failed']
        )
    
    def pause_task(self, task_id: str, reason: str = ""):
        """暂停任务"""
        self.resume_manager.pause_task(task_id, reason)
        self._running_tasks[task_id] = False
    
    def resume_task(self, task_id: str):
        """恢复任务"""
        self.resume_manager.resume_task(task_id)
        self._running_tasks[task_id] = True
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        task = self.db_manager.get_batch_crawl_task(task_id)
        if not task:
            return {'error': '任务不存在'}
        
        resume_info = self.resume_manager.get_task_resume_point(task_id)
        
        return {
            'task': task,
            'resume_info': resume_info,
            'is_running': self._running_tasks.get(task_id, False),
            'stats': self._task_stats.get(task_id, {})
        }
    
    def list_tasks(self, status_filter: str = None) -> List[BatchCrawlTask]:
        """列出所有任务"""
        return self.db_manager.list_batch_crawl_tasks(status_filter)
    
    def retry_failed_urls(self, task_id: str, max_retry_count: int = None) -> int:
        """重试失败的URL"""
        failed_urls = self.resume_manager.get_failed_urls_for_retry(task_id, max_retry_count)
        
        if failed_urls:
            question_ids = [url.question_id for url in failed_urls]
            affected_rows = self.resume_manager.reset_failed_to_pending(task_id, question_ids)
            self.logger.info(f"任务 {task_id} 重置了 {affected_rows} 个失败URL为待重试状态")
            return affected_rows
        
        return 0
    
    async def cleanup(self):
        """清理资源"""
        # 停止所有运行中的任务
        for task_id in list(self._running_tasks.keys()):
            self._running_tasks[task_id] = False
        
        # 关闭监控
        if self.monitor:
            self.monitor.stop_monitoring()
        
        # 关闭数据库连接
        if self.db_manager:
            self.db_manager.close()
        
        self.logger.info("批量采集管理器已清理")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取批量采集统计信息"""
        try:
            # 获取任务统计
            tasks = self.db_manager.list_batch_crawl_tasks()
            task_stats = {
                'total': len(tasks),
                'running': len([t for t in tasks if t.status == 'running']),
                'completed': len([t for t in tasks if t.status == 'completed']),
                'failed': len([t for t in tasks if t.status == 'failed'])
            }
            
            # 获取URL统计
            all_progress = self.db_manager.list_batch_crawl_progress()
            url_stats = {
                'total': len(all_progress),
                'completed': len([p for p in all_progress if p.status == 'completed']),
                'failed': len([p for p in all_progress if p.status == 'failed'])
            }
            url_stats['success_rate'] = (
                url_stats['completed'] / max(url_stats['total'], 1) * 100
            )
            
            # 获取当前运行的任务
            running_tasks = [t.task_id for t in tasks if t.status == 'running']
            
            return {
                'tasks': task_stats,
                'urls': url_stats,
                'current_running_tasks': running_tasks
            }
        except Exception as e:
            self.logger.error(f"获取统计信息失败: {e}")
            return {
                'tasks': {'total': 0, 'running': 0, 'completed': 0, 'failed': 0},
                'urls': {'total': 0, 'completed': 0, 'failed': 0, 'success_rate': 0.0},
                'current_running_tasks': []
            }