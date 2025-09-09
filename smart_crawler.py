#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能知乎爬虫

智能知乎爬虫系统
"""

import time
import asyncio
import aiohttp
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from loguru import logger
import random
from urllib.parse import urlencode

from dynamic_params_extractor import DynamicParamsExtractor
from params_pool_manager import ParamsPoolManager, ParamsRecord
from zhihu_lazyload_crawler import ZhihuLazyLoadCrawler


@dataclass
class CrawlResult:
    """爬取结果"""
    question_id: str
    success: bool
    data: Optional[Dict] = None
    error: Optional[str] = None
    params_used: Optional[int] = None
    response_time: float = 0.0
    

class SmartCrawler:
    """智能知乎爬虫"""
    
    def __init__(self, 
                 max_concurrent: int = 5,
                 user_data_dir: Optional[str] = None):
        """
        初始化智能爬虫（仅使用浏览器模拟方式）
        
        Args:
            max_concurrent: 最大并发数
            user_data_dir: Chrome用户数据目录
        """
        # 初始化爬虫，强制不使用无头浏览器
        self.legacy_crawler = ZhihuLazyLoadCrawler()
        # 初始化浏览器爬虫
        from zhihu_lazyload_crawler import BrowserFeedsCrawler
        self.browser_crawler = BrowserFeedsCrawler(headless=False)
        self.max_concurrent = max_concurrent
        self.user_data_dir = user_data_dir
        
        # 统计信息
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0
        }
        
    async def crawl_question_feeds(self, 
                                   question_id: str, 
                                   limit: int = 20, 
                                   offset: int = 0,
                                   max_retries: int = 3) -> CrawlResult:
        """
        爬取问题的feeds数据（仅使用selenium方式）
        
        Args:
            question_id: 问题ID
            limit: 每页数量（传递给selenium爬虫）
            offset: 偏移量（传递给selenium爬虫）
            max_retries: 最大重试次数
            
        Returns:
            爬取结果
        """
        start_time = time.time()
        
        for attempt in range(max_retries + 1):
            try:
                # 直接使用selenium方式爬取
                logger.info(f"🔍 使用selenium方式爬取问题 {question_id} (尝试 {attempt + 1}/{max_retries + 1})")
                return await self._selenium_crawl(question_id, start_time, limit)
                    
            except Exception as e:
                logger.error(f"❌ 爬取过程出错 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                
            # 重试前等待
            if attempt < max_retries:
                await asyncio.sleep(random.uniform(1, 3))
                
        # 所有重试失败
        response_time = time.time() - start_time
        error_msg = f"所有重试都失败，无法爬取问题 {question_id}"
        logger.error(f"❌ {error_msg}")
        return CrawlResult(
            question_id=question_id,
            success=False,
            error=error_msg,
            response_time=response_time
        )
        

        
    async def _selenium_crawl(self, question_id: str, start_time: float, limit: int = 20) -> CrawlResult:
        """
        使用浏览器模拟方式爬取问题
        
        Args:
            question_id: 问题ID
            start_time: 开始时间
            limit: 限制获取的回答数量
            
        Returns:
            爬取结果
        """
        try:
            # 使用浏览器爬虫方法
            # 设置较长的暂停时间，确保内容加载完整
            feeds_data = await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: self.browser_crawler.crawl_feeds_via_browser(question_id, max_scrolls=limit//2, pause=3.0), 
            )
            
            response_time = time.time() - start_time
            self.stats['successful_requests'] += 1
            
            if feeds_data:
                # 转换为标准格式
                answers = self.legacy_crawler.extract_answers_from_feeds(feeds_data)
                data = {
                    'data': answers,
                    'paging': {'is_end': True, 'totals': len(answers)}
                }
                logger.info(f"✅ Selenium爬取成功: {question_id}, 获取到 {len(answers)} 个回答, 耗时: {response_time:.2f}s")
                return CrawlResult(
                    question_id=question_id,
                    success=True,
                    data=data,
                    response_time=response_time
                )
            else:
                error_msg = "Selenium爬取未获取到数据"
                logger.warning(f"⚠️ {error_msg}: {question_id}")
                return CrawlResult(
                    question_id=question_id,
                    success=False,
                    error=error_msg,
                    response_time=response_time
                )
                
        except Exception as e:
            response_time = time.time() - start_time
            error_msg = f"Selenium爬取异常: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return CrawlResult(
                question_id=question_id,
                success=False,
                error=error_msg,
                response_time=response_time
            )
            
    async def batch_crawl(self, 
                         question_ids: List[str], 
                         limit: int = 20,
                         progress_callback: Optional[callable] = None) -> List[CrawlResult]:
        """
        批量爬取问题（仅使用selenium方式）
        
        Args:
            question_ids: 问题ID列表
            limit: 每页数量（传递给selenium爬虫）
            progress_callback: 进度回调函数
            
        Returns:
            爬取结果列表
        """
        logger.info(f"🚀 开始批量爬取 {len(question_ids)} 个问题（使用selenium方式）")
        
        # 创建信号量控制并发
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def crawl_with_semaphore(question_id: str, index: int) -> CrawlResult:
            async with semaphore:
                result = await self.crawl_question_feeds(question_id, limit)
                
                # 更新统计
                self.stats['total_requests'] += 1
                if not result.success:
                    self.stats['failed_requests'] += 1
                    
                # 调用进度回调
                if progress_callback:
                    progress_callback(index + 1, len(question_ids), result)
                    
                return result
                
        # 执行批量爬取
        tasks = [
            crawl_with_semaphore(question_id, i) 
            for i, question_id in enumerate(question_ids)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ 任务异常: {question_ids[i]} - {result}")
                final_results.append(CrawlResult(
                    question_id=question_ids[i],
                    success=False,
                    error=str(result)
                ))
            else:
                final_results.append(result)
                
        # 输出统计信息
        successful_count = sum(1 for r in final_results if r.success)
        logger.info(f"🎉 批量爬取完成: {successful_count}/{len(question_ids)} 成功")
        
        return final_results
        
    def get_stats(self):
        """
        获取爬虫统计信息
        
        Returns:
            统计信息字典
        """
        # 在仅Selenium模式下不需要获取参数池统计信息
        
        return {
            **self.stats,
            'success_rate': self.stats['successful_requests'] / max(self.stats['total_requests'], 1),
            'pool_stats': {}
        }
        
    def close(self):
        """关闭爬虫，释放资源"""
        # 在仅Selenium模式下不需要关闭params_extractor
        pass
            
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.close()