#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能知乎爬虫

整合动态参数获取和API批量请求的智能爬虫系统
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
                 params_db_path: str = "params_pool.db",
                 max_pool_size: int = 100,
                 max_concurrent: int = 5,
                 user_data_dir: Optional[str] = None):
        """
        初始化智能爬虫
        
        Args:
            params_db_path: 参数池数据库路径
            max_pool_size: 参数池最大容量
            max_concurrent: 最大并发数
            user_data_dir: Chrome用户数据目录
        """
        self.params_manager = ParamsPoolManager(params_db_path, max_pool_size)
        self.params_extractor = None
        self.legacy_crawler = ZhihuLazyLoadCrawler()
        self.traditional_crawler = ZhihuLazyLoadCrawler()
        self.max_concurrent = max_concurrent
        self.user_data_dir = user_data_dir
        
        # 请求配置
        self.base_url = "https://www.zhihu.com/api/v4/questions"
        self.timeout = aiohttp.ClientTimeout(total=30)
        
        # 统计信息
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'params_extracted': 0,
            'fallback_used': 0
        }
        
    async def crawl_question_feeds(self, 
                                   question_id: str, 
                                   limit: int = 20, 
                                   offset: int = 0,
                                   max_retries: int = 3) -> CrawlResult:
        """
        爬取问题的feeds数据
        
        Args:
            question_id: 问题ID
            limit: 每页数量
            offset: 偏移量
            max_retries: 最大重试次数
            
        Returns:
            爬取结果
        """
        start_time = time.time()
        
        for attempt in range(max_retries + 1):
            try:
                # 获取参数
                params_record = await self._get_valid_params(question_id)
                
                if not params_record:
                    logger.warning(f"⚠️ 无可用参数，使用传统方法爬取问题 {question_id}")
                    return await self._fallback_crawl(question_id, start_time)
                    
                # 使用API请求
                result = await self._api_request(question_id, params_record, limit, offset)
                
                if result.success:
                    self.params_manager.mark_params_used(params_record.id, True)
                    self.stats['successful_requests'] += 1
                    return result
                else:
                    self.params_manager.mark_params_used(params_record.id, False)
                    logger.warning(f"⚠️ API请求失败 (尝试 {attempt + 1}/{max_retries + 1}): {result.error}")
                    
            except Exception as e:
                logger.error(f"❌ 爬取过程出错 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                
            # 重试前等待
            if attempt < max_retries:
                await asyncio.sleep(random.uniform(1, 3))
                
        # 所有重试失败，使用传统方法
        logger.warning(f"⚠️ API方法失败，使用传统方法爬取问题 {question_id}")
        return await self._fallback_crawl(question_id, start_time)
        
    async def _get_valid_params(self, question_id: str) -> Optional[ParamsRecord]:
        """
        获取有效的反爬虫参数
        
        Args:
            question_id: 问题ID
            
        Returns:
            有效的参数记录
        """
        # 首先尝试从池中获取
        params_record = self.params_manager.get_best_params()
        
        if params_record and not params_record.is_expired:
            return params_record
            
        # 池中无可用参数，动态提取
        logger.info(f"🔄 为问题 {question_id} 动态提取参数")
        
        try:
            if not self.params_extractor:
                self.params_extractor = DynamicParamsExtractor(
                    headless=True, 
                    user_data_dir=self.user_data_dir
                )
                
            params = self.params_extractor.extract_params_from_question(question_id)
            
            if params and self.params_extractor.validate_params(params):
                # 添加到参数池
                params['question_id'] = question_id
                if self.params_manager.add_params(params):
                    self.stats['params_extracted'] += 1
                    return self.params_manager.get_best_params()
                    
        except Exception as e:
            logger.error(f"❌ 动态提取参数失败: {e}")
            
        return None
        
    async def _api_request(self, 
                          question_id: str, 
                          params_record: ParamsRecord, 
                          limit: int, 
                          offset: int) -> CrawlResult:
        """
        执行API请求
        
        Args:
            question_id: 问题ID
            params_record: 参数记录
            limit: 每页数量
            offset: 偏移量
            
        Returns:
            爬取结果
        """
        start_time = time.time()
        
        # 构建URL和参数
        url = f"{self.base_url}/{question_id}/feeds"
        
        query_params = {
            'limit': limit,
            'offset': offset,
            'order': 'default',
            'include': 'data[*].is_normal,admin_closed_comment,reward_info,is_collapsed,annotation_action,annotation_detail,collapse_reason,is_sticky,collapsed_by,suggest_edit,comment_count,can_comment,content,editable_content,attachment,voteup_count,reshipment_settings,comment_permission,created_time,updated_time,review_info,relevant_info,question,excerpt,is_labeled,paid_info,paid_info_content,relationship.is_authorized,is_author,voting,is_thanked,is_nothelp,is_recognized;data[*].mark_infos[*].url;data[*].author.follower_count,vip_info,badge[*].topics;data[*].settings.table_of_contents.enabled'
        }
        
        full_url = f"{url}?{urlencode(query_params)}"
        
        # 构建请求头
        headers = {
            'accept': '*/*',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'cache-control': 'no-cache',
            'pragma': 'no-cache',
            'sec-ch-ua': '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            **params_record.to_headers()
        }
        
        # 添加cookie
        if params_record.session_id:
            headers['cookie'] = f'z_c0={params_record.session_id}'
            
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(full_url, headers=headers) as response:
                    response_time = time.time() - start_time
                    
                    if response.status == 200:
                        data = await response.json()
                        
                        # 验证响应数据
                        if self._validate_response(data):
                            logger.info(f"✅ API请求成功: {question_id}, 耗时: {response_time:.2f}s")
                            return CrawlResult(
                                question_id=question_id,
                                success=True,
                                data=data,
                                params_used=params_record.id,
                                response_time=response_time
                            )
                        else:
                            error_msg = "响应数据格式无效"
                            logger.warning(f"⚠️ {error_msg}: {question_id}")
                            return CrawlResult(
                                question_id=question_id,
                                success=False,
                                error=error_msg,
                                params_used=params_record.id,
                                response_time=response_time
                            )
                    else:
                        error_msg = f"HTTP {response.status}: {await response.text()}"
                        logger.warning(f"⚠️ API请求失败: {error_msg}")
                        return CrawlResult(
                            question_id=question_id,
                            success=False,
                            error=error_msg,
                            params_used=params_record.id,
                            response_time=response_time
                        )
                        
        except Exception as e:
            response_time = time.time() - start_time
            error_msg = f"请求异常: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return CrawlResult(
                question_id=question_id,
                success=False,
                error=error_msg,
                params_used=params_record.id,
                response_time=response_time
            )
            
    def _validate_response(self, data: Dict) -> bool:
        """
        验证API响应数据
        
        Args:
            data: 响应数据
            
        Returns:
            数据是否有效
        """
        if not isinstance(data, dict):
            return False
            
        # 检查基本结构
        if 'data' not in data:
            return False
            
        # 检查是否有错误信息
        if 'error' in data:
            return False
            
        return True
        
    async def _fallback_crawl(self, question_id: str, start_time: float) -> CrawlResult:
        """
        传统方法爬取（降级策略）
        
        Args:
            question_id: 问题ID
            start_time: 开始时间
            
        Returns:
            爬取结果
        """
        try:
            # 使用传统爬虫方法
            # 使用正确的方法名
            feeds_data = await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: self.traditional_crawler.crawl_feeds_with_browser_headers(question_id), 
            )
            
            response_time = time.time() - start_time
            self.stats['fallback_used'] += 1
            
            if feeds_data:
                # 转换为标准格式
                answers = self.traditional_crawler.extract_answers_from_feeds(feeds_data)
                data = {
                    'data': answers,
                    'paging': {'is_end': True, 'totals': len(answers)}
                }
                logger.info(f"✅ 传统方法爬取成功: {question_id}, 耗时: {response_time:.2f}s")
                return CrawlResult(
                    question_id=question_id,
                    success=True,
                    data=data,
                    response_time=response_time
                )
            else:
                error_msg = "传统方法未获取到数据"
                logger.warning(f"⚠️ {error_msg}: {question_id}")
                return CrawlResult(
                    question_id=question_id,
                    success=False,
                    error=error_msg,
                    response_time=response_time
                )
                
        except Exception as e:
            response_time = time.time() - start_time
            error_msg = f"传统方法异常: {str(e)}"
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
        批量爬取问题
        
        Args:
            question_ids: 问题ID列表
            limit: 每页数量
            progress_callback: 进度回调函数
            
        Returns:
            爬取结果列表
        """
        logger.info(f"🚀 开始批量爬取 {len(question_ids)} 个问题")
        
        # 清理过期参数
        self.params_manager.cleanup_expired_params()
        
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
        
    def get_stats(self) -> Dict:
        """
        获取爬虫统计信息
        
        Returns:
            统计信息字典
        """
        pool_stats = self.params_manager.get_pool_stats()
        
        return {
            **self.stats,
            'success_rate': self.stats['successful_requests'] / max(self.stats['total_requests'], 1),
            'pool_stats': pool_stats
        }
        
    def close(self):
        """关闭爬虫，释放资源"""
        if self.params_extractor:
            self.params_extractor.close()
            
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.close()