#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知乎API懒加载爬虫
支持完整的分页和连续请求fetch文件
"""

import requests
import json
import time
import re
from urllib.parse import urlparse, parse_qs
from typing import List, Dict, Optional, Tuple, Any
from loguru import logger
from pathlib import Path
import argparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException
from config import ZhihuConfig
import pickle


class ZhihuLazyLoadCrawler:
    """知乎懒加载API爬虫"""

    def __init__(self):
        self.session = requests.Session()
        self.base_headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        }
        self.session.headers.update(self.base_headers)
        self.load_cookies()

        # API配置
        self.api_base_url = 'https://www.zhihu.com/api/v4/questions'
        self.feeds_include_params = (
            'data[*].is_normal,admin_closed_comment,reward_info,is_collapsed,'
            'annotation_action,annotation_detail,collapse_reason,is_sticky,'
            'collapsed_by,suggest_edit,comment_count,can_comment,content,'
            'editable_content,attachment,voteup_count,reshipment_settings,'
            'comment_permission,created_time,updated_time,review_info,'
            'relevant_info,question,excerpt,is_labeled,paid_info,'
            'paid_info_content,reaction_instruction,relationship.is_authorized,'
            'is_author,voting,is_thanked,is_nothelp;'
            'data[*].author.follower_count,vip_info,kvip_info,badge[*].topics;'
            'data[*].settings.table_of_content.enabled'
        )

    def load_cookies(self):
        """加载cookies"""
        try:
            cookie_file = Path('cookies/zhihu_cookies.json')
            with open(cookie_file, 'r', encoding='utf-8') as f:
                cookies_data = json.load(f)
                for cookie in cookies_data:
                    self.session.cookies.set(
                        cookie['name'],
                        cookie['value'],
                        domain=cookie.get('domain', '.zhihu.com'),
                        path=cookie.get('path', '/')
                    )
                logger.info(f"成功加载cookies，共{len(cookies_data)}个")
                return True
        except Exception as e:
            logger.error(f"加载cookies失败: {e}")
            return False

    def extract_question_id(self, question_url: str) -> Optional[str]:
        """从问题URL中提取问题ID"""
        try:
            if '/question/' in question_url:
                parts = question_url.split('/question/')
                if len(parts) > 1:
                    question_id = parts[1].split('/')[0].split('?')[0]
                    return question_id
            return None
        except Exception as e:
            logger.error(f"提取问题ID失败: {e}")
            return None
        
    def crawl_feeds_with_browser_headers(self, question_id: str, max_pages: int = 10,
                                       session_id: str = None, 
                                       x_zse_96: str = None,
                                       x_zst_81: str = None) -> List[Dict]:
        """使用浏览器headers连续获取多页feeds数据
        
        模拟浏览器的连续fetch请求，获取完整的问答回答列表
        
        Args:
            question_id: 问题ID
            max_pages: 最大页数
            session_id: 会话ID
            x_zse_96: 知乎反爬虫参数
            x_zst_81: 知乎反爬虫参数
            
        Returns:
            所有获取到的feeds数据列表
        """
        all_feeds = []
        current_cursor = None
        current_offset = 1  # 从offset=1开始，如用户示例
        page_count = 0
        
        logger.info(f"🚀 开始使用浏览器headers爬取问题 {question_id} 的feeds数据")
        
        while page_count < max_pages:
            logger.info(f"📖 正在获取第 {page_count + 1} 页数据...")
            
            # 获取当前页数据
            page_data = self.fetch_feeds_with_browser_headers(
                question_id=question_id,
                cursor=current_cursor,
                offset=current_offset if current_cursor is None else None,
                limit=5,
                session_id=session_id,
                x_zse_96=x_zse_96,
                x_zst_81=x_zst_81
            )
            
            if not page_data:
                logger.warning(f"⚠️ 第 {page_count + 1} 页数据获取失败，停止爬取")
                break
                
            # 提取feeds数据
            feeds_data = page_data.get('data', [])
            if not feeds_data:
                logger.info(f"📄 第 {page_count + 1} 页没有更多数据，停止爬取")
                break
                
            all_feeds.extend(feeds_data)
            logger.info(f"✅ 第 {page_count + 1} 页获取到 {len(feeds_data)} 个feed项，累计 {len(all_feeds)} 个")
            
            # 检查分页信息
            paging = page_data.get('paging', {})
            is_end = paging.get('is_end', True)
            
            if is_end:
                logger.info(f"📄 已到达最后一页，停止爬取")
                break
                
            # 获取下一页的cursor
            next_url = paging.get('next')
            if next_url:
                # 解析next URL获取cursor
                parsed_next = self.parse_next_url(next_url)
                current_cursor = parsed_next.get('cursor')
                current_offset = parsed_next.get('offset')
                
                if current_cursor:
                    logger.info(f"🔗 获取到下一页cursor: {current_cursor[:20]}...")
                elif current_offset:
                    logger.info(f"🔗 获取到下一页offset: {current_offset}")
            else:
                logger.warning(f"⚠️ 未找到下一页链接，停止爬取")
                break
                
            page_count += 1
            
            # 添加延时避免请求过快
            if page_count < max_pages:
                time.sleep(2)
                
        logger.info(f"🎉 爬取完成！共获取 {len(all_feeds)} 个feed项，{page_count + 1} 页数据")
        return all_feeds
        
    def extract_answer_details_from_feeds(self, feeds_data: List[Dict]) -> List[Dict]:
        """从feeds数据中提取回答详情
        
        Args:
            feeds_data: feeds数据列表
            
        Returns:
            回答详情列表
        """
        answers = []
        
        for feed in feeds_data:
            try:
                # 检查feed类型
                feed_type = feed.get('type', '')
                if feed_type != 'answer':
                    continue
                    
                # 提取回答基本信息
                answer_id = feed.get('id', '')
                content = feed.get('content', '')
                excerpt = feed.get('excerpt', '')
                
                # 提取作者信息
                author = feed.get('author', {})
                author_name = author.get('name', '')
                author_url_token = author.get('url_token', '')
                author_headline = author.get('headline', '')
                author_follower_count = author.get('follower_count', 0)
                
                # 提取VIP信息
                vip_info = author.get('vip_info', {})
                is_vip = vip_info.get('is_vip', False)
                
                # 提取统计信息
                voteup_count = feed.get('voteup_count', 0)
                comment_count = feed.get('comment_count', 0)
                
                # 提取时间信息
                created_time = feed.get('created_time', 0)
                updated_time = feed.get('updated_time', 0)
                
                # 提取问题信息
                question = feed.get('question', {})
                question_id = question.get('id', '')
                question_title = question.get('title', '')
                
                # 提取投票信息
                voting = feed.get('voting', 0)
                is_thanked = feed.get('is_thanked', False)
                
                answer_detail = {
                    'answer_id': answer_id,
                    'question_id': question_id,
                    'question_title': question_title,
                    'content': content,
                    'excerpt': excerpt,
                    'author': {
                        'name': author_name,
                        'url_token': author_url_token,
                        'headline': author_headline,
                        'follower_count': author_follower_count,
                        'is_vip': is_vip
                    },
                    'stats': {
                        'voteup_count': voteup_count,
                        'comment_count': comment_count,
                        'voting': voting,
                        'is_thanked': is_thanked
                    },
                    'timestamps': {
                        'created_time': created_time,
                        'updated_time': updated_time
                    },
                    'raw_feed': feed  # 保留原始数据以备需要
                }
                
                answers.append(answer_detail)
                
            except Exception as e:
                logger.error(f"解析feed数据时出错: {e}")
                continue
                
        logger.info(f"📊 从 {len(feeds_data)} 个feed中提取到 {len(answers)} 个回答详情")
        return answers

    def parse_next_url(self, next_url: str) -> Dict:
        """解析下一页URL中的参数"""
        try:
            if not next_url:
                return {}

            parsed_url = urlparse(next_url)
            params = parse_qs(parsed_url.query)

            # 提取关键参数
            result = {}
            for key, values in params.items():
                if values:
                    result[key] = values[0] if len(values) == 1 else values

            return result
        except Exception as e:
            logger.error(f"解析next URL失败: {e}")
            return {}

    def build_feeds_url(self, question_id: str, cursor: str = None,
                       offset: int = None, limit: int = 20) -> str:
        """构建feeds API URL"""
        url = f"{self.api_base_url}/{question_id}/feeds"

        params = {
            'include': self.feeds_include_params,
            'limit': str(limit),
            'order': 'default',
            'ws_qiangzhisafe': '0',
            'platform': 'desktop'
        }

        # 添加cursor或offset（优先使用cursor）
        if cursor:
            params['cursor'] = cursor
        elif offset is not None:
            params['offset'] = str(offset)

        # 手动构建URL避免编码问题
        param_str = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"{url}?{param_str}"

    def fetch_feeds_with_browser_headers(self, question_id: str, cursor: str = None, 
                                       offset: int = None, limit: int = 5, 
                                       session_id: str = None, 
                                       x_zse_93: str = "101_3_3.0",
                                       x_zse_96: str = None,
                                       x_zst_81: str = None) -> Optional[Dict]:
        """使用浏览器完整headers获取feeds数据
        
        基于浏览器fetch请求的完整实现，包含所有必要的反爬虫headers
        
        Args:
            question_id: 问题ID
            cursor: 游标参数，用于分页
            offset: 偏移量参数
            limit: 每页数量，默认5
            session_id: 会话ID
            x_zse_93: 知乎反爬虫参数
            x_zse_96: 知乎反爬虫参数
            x_zst_81: 知乎反爬虫参数
            
        Returns:
            API响应数据或None
        """
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # 构建完整的URL
                url = self._build_browser_feeds_url(
                    question_id, cursor, offset, limit, session_id
                )
                
                logger.info(f"使用浏览器headers请求feeds API (尝试 {attempt + 1}/{max_retries})")
                logger.debug(f"请求URL: {url}")
                
                # 构建完整的浏览器headers
                headers = {
                    "accept": "*/*",
                    "accept-language": "en,zh-CN;q=0.9,zh;q=0.8,de;q=0.7,zh-TW;q=0.6",
                    "priority": "u=1, i",
                    "sec-ch-ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"macOS"',
                    "sec-fetch-dest": "empty",
                    "sec-fetch-mode": "cors",
                    "sec-fetch-site": "same-origin",
                    "x-requested-with": "fetch",
                    "x-zse-93": x_zse_93,
                    "Referer": f"https://www.zhihu.com/question/{question_id}",
                    "Referrer-Policy": "strict-origin-when-cross-origin"
                }
                
                # 添加可选的反爬虫headers
                if x_zse_96:
                    headers["x-zse-96"] = x_zse_96
                if x_zst_81:
                    headers["x-zst-81"] = x_zst_81
                    
                # 发送请求
                response = self.session.get(url, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    feeds_data = data.get('data', [])
                    logger.info(f"✅ 获取到 {len(feeds_data)} 个feed项")
                    
                    # 记录分页信息
                    paging = data.get('paging', {})
                    if paging:
                        logger.info(f"📄 分页信息: is_end={paging.get('is_end', False)}, next={paging.get('next', 'N/A')}")
                    
                    return data
                    
                elif response.status_code == 403:
                    logger.warning(f"❌ API访问被拒绝: {response.status_code}")
                    try:
                        error_data = response.json()
                        if 'error' in error_data:
                            logger.warning(f"错误信息: {error_data['error'].get('message', 'Unknown error')}")
                    except:
                        logger.warning(f"响应内容: {response.text[:200]}")
                    return None
                    
                else:
                    logger.warning(f"⚠️ API返回异常状态: {response.status_code}")
                    logger.debug(f"响应内容: {response.text[:200]}")
                    if attempt == max_retries - 1:
                        return None
                        
            except requests.exceptions.RequestException as e:
                logger.error(f"网络请求失败 (尝试 {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    return None
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败 (尝试 {attempt + 1}): {e}")
                logger.debug(f"响应内容: {response.text[:200] if 'response' in locals() else 'N/A'}")
                if attempt == max_retries - 1:
                    return None
            except Exception as e:
                logger.error(f"未知错误 (尝试 {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    return None
                    
            # 失败后等待重试
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2
                logger.info(f"等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
                
        return None
        
    def _build_browser_feeds_url(self, question_id: str, cursor: str = None,
                               offset: int = None, limit: int = 5, 
                               session_id: str = None) -> str:
        """构建浏览器风格的feeds API URL
        
        Args:
            question_id: 问题ID
            cursor: 游标参数
            offset: 偏移量参数  
            limit: 每页数量
            session_id: 会话ID
            
        Returns:
            完整的API URL
        """
        url = f"{self.api_base_url}/{question_id}/feeds"
        
        # 使用与浏览器fetch相同的include参数
        include_params = (
            "data%5B%2A%5D.is_normal%2Cadmin_closed_comment%2Creward_info%2Cis_collapsed%2C"
            "annotation_action%2Cannotation_detail%2Ccollapse_reason%2Cis_sticky%2C"
            "collapsed_by%2Csuggest_edit%2Ccomment_count%2Ccan_comment%2Ccontent%2C"
            "editable_content%2Cattachment%2Cvoteup_count%2Creshipment_settings%2C"
            "comment_permission%2Ccreated_time%2Cupdated_time%2Creview_info%2C"
            "relevant_info%2Cquestion%2Cexcerpt%2Cis_labeled%2Cpaid_info%2C"
            "paid_info_content%2Creaction_instruction%2Crelationship.is_authorized%2C"
            "is_author%2Cvoting%2Cis_thanked%2Cis_nothelp%3Bdata%5B%2A%5D.author.follower_count%2C"
            "vip_info%2Ckvip_info%2Cbadge%5B%2A%5D.topics%3Bdata%5B%2A%5D.settings.table_of_content.enabled"
        )
        
        params = {
            'include': include_params,
            'limit': str(limit),
            'order': 'default',
            'platform': 'desktop',
            'ws_qiangzhisafe': '0'
        }
        
        # 添加cursor或offset
        if cursor:
            params['cursor'] = cursor
        elif offset is not None:
            params['offset'] = str(offset)
            
        # 添加session_id
        if session_id:
            params['session_id'] = session_id
            
        # 构建URL
        param_str = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"{url}?{param_str}"

    def fetch_feeds_page(self, question_id: str, cursor: str = None,
                        offset: int = None, limit: int = 20) -> Optional[Dict]:
        """获取feeds页面数据"""
        max_retries = 3

        for attempt in range(max_retries):
            try:
                url = self.build_feeds_url(question_id, cursor, offset, limit)
                logger.info(f"请求feeds API (尝试 {attempt + 1}/{max_retries})")
                logger.debug(f"请求URL: {url}")

                # 设置headers
                headers = self.base_headers.copy()
                headers['Referer'] = f'https://www.zhihu.com/question/{question_id}'
                headers['X-Requested-With'] = 'fetch'

                response = self.session.get(url, headers=headers, timeout=30)

                if response.status_code == 200:
                    data = response.json()

                    # 检查是否有数据
                    feeds_data = data.get('data', [])
                    logger.info(f"✅ 获取到 {len(feeds_data)} 个feed项")

                    # 检查session信息
                    session_info = data.get('session', {})
                    session_id = session_info.get('id', '')
                    if session_id:
                        logger.info(f"🔑 Session ID: {session_id}")

                    return data

                elif response.status_code == 403:
                    logger.warning(f"❌ API访问被拒绝: {response.status_code}")
                    error_data = response.json()
                    if 'error' in error_data:
                        logger.warning(f"错误信息: {error_data['error'].get('message', 'Unknown error')}")
                    return None

                else:
                    logger.warning(f"⚠️ API返回异常状态: {response.status_code}")
                    if attempt == max_retries - 1:
                        return None

            except requests.exceptions.RequestException as e:
                logger.error(f"网络请求失败 (尝试 {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    return None
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败 (尝试 {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    return None
            except Exception as e:
                logger.error(f"未知错误 (尝试 {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    return None

            # 失败后等待后重试
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2
                logger.info(f"等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)

        return None

    def crawl_all_feeds_lazyload(self, question_id: str, max_feeds: int = None) -> List[Dict]:
        """使用懒加载方式爬取所有feeds数据"""
        all_feeds = []
        page_count = 0
        cursor = None
        offset = 0

        logger.info(f"🚀 开始懒加载爬取问题 {question_id} 的feeds")
        logger.info(f"📊 最大feeds限制: {max_feeds if max_feeds else '无限制'}")

        while True:
            page_count += 1
            logger.info(f"\n📄 获取第 {page_count} 页数据")
            logger.info(f"🔄 Cursor: {cursor}, Offset: {offset}")

            # 获取当前页数据
            page_data = self.fetch_feeds_page(question_id, cursor=cursor, offset=offset, limit=20)
            if not page_data:
                logger.error(f"❌ 获取第 {page_count} 页数据失败")
                break

            # 解析feeds数据
            feeds_data = page_data.get('data', [])
            logger.info(f"📦 本页获取到 {len(feeds_data)} 个feed项")

            # 添加到总集合
            all_feeds.extend(feeds_data)

            # 检查是否达到最大数量限制
            if max_feeds and len(all_feeds) >= max_feeds:
                logger.info(f"✅ 已达到最大feeds数量限制: {max_feeds}")
                all_feeds = all_feeds[:max_feeds]
                break

            # 解析分页信息
            paging = page_data.get('paging', {})
            is_end = paging.get('is_end', True)
            next_url = paging.get('next', '')

            logger.info(f"🔍 分页信息: is_end={is_end}")

            if is_end:
                logger.info(f"🎯 已到达最后一页")
                break

            # 解析下一页参数
            next_params = self.parse_next_url(next_url)

            # 更新cursor和offset
            if 'cursor' in next_params:
                cursor = next_params['cursor']
                logger.info(f"📌 更新cursor: {cursor}")
            elif 'offset' in next_params:
                offset = int(next_params['offset'])
                logger.info(f"📌 更新offset: {offset}")
            else:
                # 如果没有明确的下一页参数，增加offset
                offset += len(feeds_data)
                logger.info(f"📌 递增offset: {offset}")

            # 添加延时避免请求过快
            time.sleep(2)

            # 安全检查
            if page_count >= 100:  # 最多100页
                logger.warning(f"⚠️ 已达到最大页数限制: {page_count}")
                break

        logger.info(f"\n🎉 懒加载爬取完成!")
        logger.info(f"📊 总共获取到 {len(all_feeds)} 个feeds")
        logger.info(f"📄 共请求了 {page_count} 页")

        return all_feeds

    def extract_answers_from_feeds(self, feeds_data: List[Dict]) -> List[Dict]:
        """从feeds数据中提取答案（requests模式）"""
        answers = []
        for feed_item in feeds_data:
            try:
                if feed_item.get('target_type') != 'answer':
                    continue
                target = feed_item.get('target', {})
                if not target:
                    continue
                answer_info = {
                    'answer_id': str(target.get('id', '')),
                    'content': target.get('content', ''),
                    'excerpt': target.get('excerpt', ''),
                    'voteup_count': target.get('voteup_count', 0),
                    'comment_count': target.get('comment_count', 0),
                    'created_time': target.get('created_time', 0),
                    'updated_time': target.get('updated_time', 0),
                    'author': target.get('author', {}).get('name', ''),
                    'author_url_token': target.get('author', {}).get('url_token', ''),
                    'question_id': target.get('question', {}).get('id', ''),
                    'question_title': target.get('question', {}).get('title', ''),
                    'is_author': target.get('relationship', {}).get('is_author', False)
                }
                answers.append(answer_info)
            except Exception as e:
                logger.warning(f"解析feed项失败: {e}")
                continue
        logger.info(f"📝 从feeds中提取到 {len(answers)} 个答案")
        return answers

    def test_lazyload_ability(self, question_id: str) -> Dict:
        """测试懒加载能力（requests模式）"""
        logger.info(f"🧪 测试问题 {question_id} 的懒加载能力")
        first_page = self.fetch_feeds_page(question_id, limit=5)
        if not first_page:
            return {'success': False, 'error': '无法获取第一页数据'}
        paging = first_page.get('paging', {})
        has_paging = bool(paging)
        has_next = bool(paging.get('next'))
        is_end = paging.get('is_end', True)
        next_page_success = False
        if not is_end and has_next:
            next_params = self.parse_next_url(paging['next'])
            cursor = next_params.get('cursor')
            offset = next_params.get('offset')
            if cursor or offset:
                next_page = self.fetch_feeds_page(
                    question_id,
                    cursor=cursor,
                    offset=int(offset) if offset else None,
                    limit=5
                )
                next_page_success = bool(next_page)
        result = {
            'success': True,
            'first_page_feeds': len(first_page.get('data', [])),
            'has_paging': has_paging,
            'has_next': has_next,
            'is_end': is_end,
            'next_page_success': next_page_success,
            'session_id': first_page.get('session', {}).get('id', ''),
            'lazyload_supported': has_paging and has_next and not is_end,
            'continuous_request_supported': next_page_success
        }
        logger.info("📊 懒加载能力测试结果:")
        for key, value in result.items():
            logger.info(f"  {key}: {value}")
        return result

    def save_feeds_data(self, feeds_data: List[Dict], filename: str) -> bool:
        """保存feeds数据到文件（自动创建输出目录）"""
        try:
            try:
                p = Path(filename)
                if p.parent and str(p.parent) not in ("", "."):
                    p.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.debug(f"创建输出目录失败（继续尝试保存文件）: {e}")
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(feeds_data, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ feeds数据已保存到: {filename}")
            return True
        except Exception as e:
            logger.error(f"保存feeds数据失败: {e}")
            return False

    def extract_answers_from_feeds(self, feeds_data: List[Dict]) -> List[Dict]:
        """从feeds数据中提取答案（browser模式辅助）"""
        answers = []
        for feed_item in feeds_data:
            try:
                if feed_item.get('target_type') != 'answer':
                    continue
                target = feed_item.get('target', {})
                if not target:
                    continue
                answer_info = {
                    'answer_id': str(target.get('id', '')),
                    'content': target.get('content', ''),
                    'excerpt': target.get('excerpt', ''),
                    'voteup_count': target.get('voteup_count', 0),
                    'comment_count': target.get('comment_count', 0),
                    'created_time': target.get('created_time', 0),
                    'updated_time': target.get('updated_time', 0),
                    'author': target.get('author', {}).get('name', ''),
                    'author_url_token': target.get('author', {}).get('url_token', ''),
                    'question_id': target.get('question', {}).get('id', ''),
                    'question_title': target.get('question', {}).get('title', ''),
                    'is_author': target.get('relationship', {}).get('is_author', False)
                }
                answers.append(answer_info)
            except Exception as e:
                logger.warning(f"解析feed项失败: {e}")
                continue
        logger.info(f"📝 从feeds中提取到 {len(answers)} 个答案")
        return answers

# =============== 新增：浏览器上下文抓取方案（方案A） ===============
class BrowserFeedsCrawler:
    """使用浏览器上下文触发前端fetch并通过CDP抓取feeds响应"""

    def __init__(self, headless: bool = None):
        self.config = ZhihuConfig
        self.headless = self.config.HEADLESS if headless is None else headless
        self.driver = None
        self._init_driver()

    def _init_driver(self):
        """初始化WebDriver，优先使用系统Chrome目录，失败时使用临时目录"""
        # 统一配置Options的函数
        def configure_options(use_temp_dir=False, temp_dir_path=None):
            options = Options()
            if self.headless:
                options.add_argument('--headless=new')
            
            # 窗口大小
            if isinstance(self.config.WINDOW_SIZE, tuple) and len(self.config.WINDOW_SIZE) == 2:
                w, h = self.config.WINDOW_SIZE
                options.add_argument(f"--window-size={w},{h}")
            elif isinstance(self.config.WINDOW_SIZE, str):
                options.add_argument(f"--window-size={self.config.WINDOW_SIZE}")
            
            # 基础配置
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            # 规避自动化特征
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # 设置语言和UA
            try:
                ua = self.config.USER_AGENTS[0]
                options.add_argument(f"--user-agent={ua}")
            except Exception:
                pass
            options.add_argument('--lang=zh-CN,zh;q=0.9,en;q=0.8')
            
            # 性能日志
            try:
                options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
            except Exception:
                pass
            
            # 用户数据目录配置
            if use_temp_dir and temp_dir_path:
                options.add_argument(f"--user-data-dir={str(temp_dir_path)}")
                logger.info(f"使用临时Chrome配置目录: {temp_dir_path}")
            else:
                user_data_dir = Path.home() / 'Library' / 'Application Support' / 'Google' / 'Chrome'
                if user_data_dir.exists():
                    options.add_argument(f"--user-data-dir={str(user_data_dir)}")
                    options.add_argument("--profile-directory=Default")
                    logger.info(f"尝试使用本地Chrome用户数据目录: {user_data_dir}")
            
            return options

        def setup_webdriver_fingerprint(driver):
            """设置WebDriver指纹隐藏"""
            try:
                driver.execute_cdp_cmd(
                    "Page.addScriptToEvaluateOnNewDocument",
                    {
                        "source": """
                        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                        Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
                        Object.defineProperty(navigator, 'platform', { get: () => 'MacIntel' });
                        window.chrome = { runtime: {} };
                        """
                    }
                )
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            except Exception:
                pass

        # 第一次尝试：使用系统Chrome目录
        try:
            options = configure_options(use_temp_dir=False)
            self.driver = webdriver.Chrome(options=options)
            setup_webdriver_fingerprint(self.driver)
            logger.info("✅ 成功初始化Chrome（使用系统用户数据目录）")
        except Exception as e:
            msg = str(e)
            if 'is already in use' in msg or 'user data directory is already in use' in msg:
                logger.warning("系统Chrome用户数据目录被占用，回退到临时目录...")
                # 第二次尝试：使用临时目录
                try:
                    import tempfile
                    tmp_base = Path(tempfile.mkdtemp(prefix="zhihu_tmp_profile_"))
                    options = configure_options(use_temp_dir=True, temp_dir_path=tmp_base)
                    self.driver = webdriver.Chrome(options=options)
                    setup_webdriver_fingerprint(self.driver)
                    logger.info("✅ 成功初始化Chrome（使用临时用户数据目录）")
                except Exception as e2:
                    logger.warning(f"Selenium Manager启动失败，尝试webdriver_manager: {e2}")
                    # 第三次尝试：使用webdriver_manager
                    try:
                        driver_path = ChromeDriverManager().install()
                        dp = Path(driver_path)
                        if dp.name.startswith("THIRD_PARTY_NOTICES"):
                            candidate = dp.parent / "chromedriver"
                            service = Service(str(candidate if candidate.exists() else dp))
                        else:
                            service = Service(str(dp))
                        self.driver = webdriver.Chrome(service=service, options=options)
                        setup_webdriver_fingerprint(self.driver)
                        logger.info("✅ 成功初始化Chrome（使用webdriver_manager）")
                    except Exception as e3:
                        logger.error(f"初始化Chrome失败: {e3}")
                        raise
            else:
                logger.warning(f"Selenium Manager启动失败，尝试webdriver_manager: {e}")
                # 直接尝试webdriver_manager
                try:
                    driver_path = ChromeDriverManager().install()
                    dp = Path(driver_path)
                    if dp.name.startswith("THIRD_PARTY_NOTICES"):
                        candidate = dp.parent / "chromedriver"
                        service = Service(str(candidate if candidate.exists() else dp))
                    else:
                        service = Service(str(dp))
                    options = configure_options(use_temp_dir=False)
                    self.driver = webdriver.Chrome(service=service, options=options)
                    setup_webdriver_fingerprint(self.driver)
                    logger.info("✅ 成功初始化Chrome（使用webdriver_manager）")
                except Exception as e2:
                    logger.error(f"初始化Chrome失败: {e2}")
                    raise

        # 启用Network以便后续抓body
        try:
            self.driver.execute_cdp_cmd('Network.enable', {})
        except Exception as e:
            logger.warning(f"启用CDP Network失败: {e}")

    def close(self):
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass

    def _load_cookies_to_driver(self) -> bool:
        """从cookies/zhihu_cookies.json加载到浏览器会话"""
        cookie_file = Path(self.config.COOKIES_FILE)
        try:
            if not cookie_file.exists():
                logger.warning(f"未找到Cookie文件: {cookie_file}")
                return False
            # 先打开主域，才能设置cookie
            self.driver.get(self.config.BASE_URL)
            time.sleep(1)
            with open(cookie_file, 'r', encoding='utf-8') as f:
                cookies_data = json.load(f)
            loaded_cdp = 0
            loaded = 0
            for c in cookies_data:
                try:
                    name = c.get('name')
                    value = c.get('value')
                    if not name or value is None:
                        continue
                    domain_raw = c.get('domain') or '.zhihu.com'
                    domain_clean = domain_raw.lstrip('.')
                    path = c.get('path', '/')
                    secure = bool(c.get('secure', True))
                    # 处理 sameSite
                    samesite_raw = c.get('sameSite') or c.get('samesite')
                    ss_map = {
                        'no_restriction': 'None',
                        'none': 'None',
                        'None': 'None',
                        'lax': 'Lax',
                        'Lax': 'Lax',
                        'strict': 'Strict',
                        'Strict': 'Strict',
                        'unspecified': None,
                        'unspecified_same_site': None
                    }
                    ss_val = ss_map.get(samesite_raw, samesite_raw)
                    # SameSite=None 时必须 secure=True
                    if ss_val == 'None' and not secure:
                        secure = True
                    http_only = c.get('httpOnly')
                    # 过期时间（秒）
                    expiry = None
                    if c.get('expiry'):
                        expiry = int(c['expiry'])
                    elif c.get('expires'):
                        try:
                            expiry = int(c['expires'])
                        except Exception:
                            expiry = None
                    # 优先使用CDP设置cookie（可设置httpOnly）
                    try:
                        params = {
                            'name': name,
                            'value': value,
                            'domain': domain_clean,
                            'path': path,
                            'secure': secure,
                        }
                        if expiry:
                            params['expires'] = expiry
                        if isinstance(http_only, bool):
                            params['httpOnly'] = http_only
                        if ss_val in {'Strict', 'Lax', 'None'}:
                            params['sameSite'] = ss_val
                        ok = self.driver.execute_cdp_cmd('Network.setCookie', params)
                        if ok and ok.get('success'):
                            loaded_cdp += 1
                            continue
                    except Exception as e_cdp:
                        logger.debug(f"CDP设置cookie失败 name={name} domain={domain_clean}: {e_cdp}")
                    # 回退：Selenium add_cookie
                    ck = {
                        'name': name,
                        'value': value,
                        'domain': domain_raw,
                        'path': path,
                        'secure': secure
                    }
                    if expiry:
                        ck['expiry'] = expiry
                    if ss_val in {'Strict', 'Lax', 'None'}:
                        ck['sameSite'] = ss_val
                    try:
                        self.driver.add_cookie(ck)
                        loaded += 1
                        continue
                    except Exception as e1:
                        try:
                            if isinstance(ck.get('domain'), str) and ck['domain'].startswith('.'):
                                ck2 = dict(ck)
                                ck2['domain'] = ck['domain'].lstrip('.')
                                self.driver.add_cookie(ck2)
                                loaded += 1
                                continue
                        except Exception as e2:
                            logger.debug(f"添加cookie失败 name={name} domain={ck.get('domain')}: {e1} | fallback: {e2}")
                            pass
                except Exception as e:
                    logger.debug(f"跳过无法设置的cookie {c.get('name')}: {e}")
                    continue
            logger.info(f"成功注入 cookies到浏览器：CDP={loaded_cdp}，Selenium={loaded}")
            # 刷新以便cookie生效
            self.driver.get(self.config.BASE_URL)
            time.sleep(1)
            return (loaded_cdp + loaded) > 0
        except Exception as e:
            logger.error(f"加载浏览器cookies失败: {e}")
            return False

    def _persist_cookies(self, driver=None) -> bool:
        """将当前浏览器会话cookies持久化到配置路径(JSON)与cache目录(Pickle)"""
        try:
            drv = driver or self.driver
            if drv is None:
                logger.warning("无法保存cookies: driver未初始化")
                return False
            cookies = drv.get_cookies()
            if not isinstance(cookies, list) or not cookies:
                logger.warning("无法保存cookies: 未从浏览器获取到任何cookie")
                return False
            # 保存JSON
            json_path = Path(self.config.COOKIES_FILE)
            json_path.parent.mkdir(parents=True, exist_ok=True)
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            # 兼容：再保存一份pickle，便于其他模块复用
            pkl_path = Path('cache/zhihu_cookies.pkl')
            pkl_path.parent.mkdir(parents=True, exist_ok=True)
            with open(pkl_path, 'wb') as pf:
                pickle.dump(cookies, pf)
            # 简要提示关键cookie
            z = next((c.get('value','') for c in cookies if c.get('name')=='z_c0'), '')
            logger.info(f"✅ 已保存登录cookies：JSON->{json_path}，PKL->{pkl_path}（z_c0长度={len(z)}）")
            return True
        except Exception as e:
            logger.warning(f"保存cookies失败: {e}")
            return False

    def _scroll_to_load(self, times: int = 1, pause: float = 2.0):
        for _ in range(times):
            try:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            except WebDriverException:
                pass
            time.sleep(pause)

    def _soft_rollback(self, percent: float = 0.08, pause: float = 1.5):
        """轻量回滚：上滚页面高度的一定比例后再下滚，触发重新懒加载"""
        try:
            current_height = self.driver.execute_script("return document.body.scrollHeight")
            current_scroll_position = self.driver.execute_script("return window.pageYOffset")
            delta = max(50, current_height * float(percent))
            new_scroll_position = max(0, current_scroll_position - delta)
            logger.info(f"↩️ 触发软回滚：上滚 {delta:.0f}px 到 {new_scroll_position:.0f}，随后再次下滑")
            self.driver.execute_script(f"window.scrollTo(0, {new_scroll_position});")
            time.sleep(pause)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(max(1.0, pause - 0.2))
        except Exception as e:
            logger.debug(f"软回滚执行失败：{e}")

    def _collect_feeds_from_perf_logs(self, question_id: str, seen_ids: set) -> list:
        """从performance日志中收集本轮新出现的feeds响应体"""
        collected = []
        debug_sample = []
        try:
            logs = self.driver.get_log('performance')
        except Exception as e:
            logger.debug(f"读取performance日志失败: {e}")
            return collected
        for entry in logs:
            try:
                msg = json.loads(entry.get('message', '{}'))
                message = msg.get('message', {})
                method = message.get('method')
                if method != 'Network.responseReceived':
                    continue
                params = message.get('params', {})
                response = params.get('response', {})
                url: str = response.get('url', '')
                ctype = (response.get('headers', {}) or {}).get('content-type', '')
                # 记录一些样本URL用于调试
                if ("zhihu.com" in url or "/api/" in url) and len(debug_sample) < 8:
                    debug_sample.append(f"{ctype} | {url}")
                # 支持 feeds 与 answers 以及更广泛的问题API路径
                base_match = (
                    f"/api/v4/questions/{question_id}/" in url or
                    f"/api/v5/questions/{question_id}/" in url or
                    f"/next/api/v4/questions/{question_id}/" in url or
                    f"/next-api/v4/questions/{question_id}/" in url or
                    f"/api/v4/questions/{question_id}?" in url
                )
                if not base_match:
                    continue
                request_id = params.get('requestId')
                if not request_id or request_id in seen_ids:
                    continue
                # 拉取body
                try:
                    body = self.driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': request_id})
                    text = body.get('body', '')
                    if not text:
                        continue
                    data = json.loads(text)
                    collected.append((request_id, data))
                except Exception as e:
                    logger.debug(f"获取响应体失败 requestId={request_id}: {e}")
                    continue
            except Exception:
                continue
        if debug_sample:
            logger.debug("样本响应URL: \n" + "\n".join(debug_sample))
        return collected

    def _fetch_first_page_fallback(self, question_id: str) -> List[Dict[str, Any]]:
        """在页面上下文直接fetch首页feeds，作为回退方案"""
        try:
            helper = ZhihuLazyLoadCrawler()
            url = helper.build_feeds_url(question_id=question_id, cursor=None, offset=0, limit=20)
            js = (
                "return fetch(arguments[0], {credentials:'include'})"
                ".then(r => r.text())"
                ".then(t => t)"
                ".catch(e => JSON.stringify({__err: String(e && e.message || e)}));"
            )
            text = self.driver.execute_script(js, url)
            if not text:
                return []
            try:
                data = json.loads(text)
            except Exception:
                # 可能返回HTML或错误
                return []
            if isinstance(data, dict):
                items = data.get('data') or []
                if isinstance(items, list):
                    logger.info(f"回退fetch获取到首页 items={len(items)}")
                    return items
            return []
        except Exception as e:
            logger.debug(f"回退fetch失败: {e}")
            return []

    # 新增：手动登录保障流程
    def _ensure_logged_in_manually(self, driver, timeout_sec: int = 180) -> bool:
        """
        引导用户在可见的浏览器中完成知乎登录，并等待登录态生效。
        返回是否检测到登录成功（依据 z_c0 cookie 的形态判断）。
        """
        try:
            logger.info(f"🔐 检测到可能未登录，准备进入手动登录流程（最长等待 {timeout_sec}s）")
            # 访问首页，便于用户登录
            try:
                driver.get("https://www.zhihu.com/")
            except Exception as e:
                logger.warning(f"打开知乎首页失败: {e}")
            start = time.time()
            last_report = -999
            while time.time() - start < timeout_sec:
                try:
                    cookies = {c.get('name'): c.get('value', '') for c in driver.get_cookies()}
                    z = cookies.get('z_c0', '')
                    # 经验：有效的 z_c0 一般以 '2|' 开头且长度较长（>60）
                    if z and (z.startswith('2|') or len(z) > 60) and 'v10' not in z:
                        logger.info(f"✅ 检测到登录cookie z_c0，长度={len(z)}，判定已登录")
                        try:
                            self._persist_cookies(driver)
                        except Exception as se:
                            logger.debug(f"登录成功但保存cookies时出现问题: {se}")
                        return True
                except Exception as ie:
                    logger.debug(f"检查登录cookie异常: {ie}")
                # 每5秒输出一次剩余时间提示
                remain = int(timeout_sec - (time.time() - start))
                if remain // 5 != last_report // 5:
                    logger.info(f"请在已打开的浏览器窗口中完成登录（剩余约 {remain}s）……")
                    last_report = remain
                time.sleep(1.5)
            logger.warning("手动登录等待超时，未检测到有效的 z_c0 cookie")
            return False
        except Exception as e:
            logger.error(f"手动登录流程异常: {e}")
            return False

    def crawl_feeds_via_browser(self, question_id: str, max_scrolls: int = 6, pause: float = 2.5, stop_when_is_end: bool = True, expected_min_per_scroll: int = 8, verify_end_with_rollback: bool = True, rollback_percent: float = 0.1) -> List[Dict[str, Any]]:
        try:
            if not self._load_cookies_to_driver():
                logger.warning("未成功注入cookies，可能会触发登录/风控")
            
            # 新增：在正式访问问题页前，主动检测登录态，不足则引导手动登录
            try:
                self.driver.get(self.config.BASE_URL)
                time.sleep(1.5)
                cookies_map = {c.get('name'): c.get('value', '') for c in self.driver.get_cookies()}
                z = cookies_map.get('z_c0', '')
                logged_in = bool(z and (z.startswith('2|') or len(z) > 60) and 'v10' not in z)
                if logged_in:
                    # 若检测到已登录（例如复用系统Chrome登录态），也立即保存一次cookies，便于API/后续流程使用
                    try:
                        self._persist_cookies(self.driver)
                    except Exception as se:
                        logger.debug(f"预检已登录但保存cookies时出现问题: {se}")
            except Exception as e:
                logger.debug(f"预检登录态异常: {e}")
                logged_in = False
            if not logged_in:
                logger.info("预检未检测到有效登录态，进入手动登录流程……")
                did_manual_login = self._ensure_logged_in_manually(self.driver, timeout_sec=180)
                if not did_manual_login:
                    logger.warning("手动登录失败或超时，继续尝试进行有限抓取（可能受限于未登录状态）")
                else:
                    # 登录成功已在 _ensure_logged_in_manually 中持久化cookies
                    logged_in = True

            q_url = f"{self.config.BASE_URL}/question/{question_id}"
            logger.info(f"打开问题页: {q_url}")
            self.driver.get(q_url)
            time.sleep(2)

            seen_request_ids = set()
            all_items = []
            is_end_flag = False

            for i in range(max_scrolls):
                logger.info(f"下拉触发懒加载， 第 {i+1}/{max_scrolls} 次")
                self._scroll_to_load(times=1, pause=pause)
                try:
                    self._persist_cookies(self.driver)
                except Exception as e:
                    logger.debug(f"滚动后持久化cookies失败: {e}")
                
                # 初始化本轮统计，避免在无新响应时未定义
                round_items_count = 0
                round_detected_is_end = False
                
                # 收集本轮新响应
                newly = self._collect_feeds_from_perf_logs(question_id, seen_request_ids)
                if newly:
                    logger.info(f"捕获到 {len(newly)} 个feeds响应")
                    
                    round_items_count = 0
                    round_detected_is_end = False
                    for req_id, payload in newly:
                        seen_request_ids.add(req_id)
                        # 兼容部分接口直接返回 list 的情况
                        if isinstance(payload, list):
                            page_items = payload
                            paging = {}
                        elif isinstance(payload, dict):
                            page_items = payload.get('data', []) or []
                            paging = (payload.get('paging') or {}) if isinstance(payload.get('paging'), dict) else {}
                        else:
                            page_items, paging = [], {}
                        all_items.extend(page_items)
                        round_items_count += len(page_items)
                        if stop_when_is_end and isinstance(paging, dict) and paging.get('is_end'):
                            round_detected_is_end = True
                            is_end_flag = True
                    
                    # 若没有新响应，尝试再次等待一小会
                    if not newly:
                        time.sleep(1)

                    # 少于预期条数，则触发一次回滚重试
                    if expected_min_per_scroll and round_items_count < expected_min_per_scroll:
                        logger.info(f"⚠️ 本轮新增 {round_items_count} 条 < 预期 {expected_min_per_scroll} 条，触发回滚重试一次……")
                        try:
                            self._soft_rollback(percent=rollback_percent, pause=max(1.2, pause - 0.3))
                            try:
                                self._persist_cookies(self.driver)
                            except Exception as e:
                                logger.debug(f"回滚后持久化cookies失败: {e}")
                            newly_retry = self._collect_feeds_from_perf_logs(question_id, seen_request_ids)
                            added_retry = 0
                            for req_id, payload in newly_retry:
                                seen_request_ids.add(req_id)
                                if isinstance(payload, list):
                                    page_items = payload
                                    paging = {}
                                elif isinstance(payload, dict):
                                    page_items = payload.get('data', []) or []
                                    paging = (payload.get('paging') or {}) if isinstance(payload.get('paging'), dict) else {}
                                else:
                                    page_items, paging = [], {}
                                all_items.extend(page_items)
                                added_retry += len(page_items)
                                if stop_when_is_end and isinstance(paging, dict) and paging.get('is_end'):
                                    round_detected_is_end = True
                                    is_end_flag = True
                            logger.info(f"回滚重试新增 {added_retry} 条")
                            round_items_count += added_retry
                        except Exception as e:
                            logger.debug(f"回滚重试异常: {e}")

                    # 若检测到 is_end，则做一次回滚验证，避免误判
                    if stop_when_is_end and round_detected_is_end and verify_end_with_rollback:
                        logger.info("🧪 检测到 paging.is_end=True，执行一次回滚验证……")
                        prev_len = len(all_items)
                        try:
                            self._soft_rollback(percent=max(rollback_percent, 0.12), pause=max(1.2, pause))
                            try:
                                self._persist_cookies(self.driver)
                            except Exception as e:
                                logger.debug(f"回滚后持久化cookies失败: {e}")
                            newly_verify = self._collect_feeds_from_perf_logs(question_id, seen_request_ids)
                            verify_added = 0
                            verify_is_end_still_true = True
                            for req_id, payload in newly_verify:
                                seen_request_ids.add(req_id)
                                if isinstance(payload, list):
                                    page_items = payload
                                    paging = {}
                                elif isinstance(payload, dict):
                                    page_items = payload.get('data', []) or []
                                    paging = (payload.get('paging') or {}) if isinstance(payload.get('paging'), dict) else {}
                                else:
                                    page_items, paging = [], {}
                                all_items.extend(page_items)
                                verify_added += len(page_items)
                                if isinstance(paging, dict) and not paging.get('is_end'):
                                    verify_is_end_still_true = False
                            logger.info(f"回滚验证新增 {verify_added} 条，is_end 仍为 {verify_is_end_still_true}")
                            # 若回滚后仍无新增或仍提示 is_end，则确认结束
                            if verify_added == 0 and verify_is_end_still_true:
                                logger.info("✅ 回滚验证后仍为结束状态，停止滚动")
                                break
                            else:
                                # 有新增或 is_end 变为 False，继续后续滚动
                                is_end_flag = False
                        except Exception as e:
                            logger.debug(f"回滚验证异常: {e}")
                            # 验证失败时保守退出
                            break

                    if is_end_flag:
                        logger.info("检测到paging.is_end=True，结束")
                        break

                    # 若没有新响应，再等待一小会再继续
                    if not newly and round_items_count == 0:
                        time.sleep(0.8)
            
            # 循环结束后的处理逻辑
            if not all_items:
                # 回退：直接在页面上下文fetch首页（仅一次）
                fallback_items = self._fetch_first_page_fallback(question_id)
                if fallback_items:
                    all_items.extend(fallback_items)

            # 仍无数据则引导用户手动登录后重试一轮（如果之前尚未手动登录）
            if not all_items and not logged_in:
                logger.info("📥 尝试进入手动登录回退流程以获取有效登录态……")
                logged = self._ensure_logged_in_manually(self.driver, timeout_sec=180)
                if logged:
                    # 登录完成后重新访问起始页，进行少量滚动采集
                    try:
                        self.driver.get(q_url)
                        time.sleep(1.5)
                        # 保存登录后的cookies
                        self._persist_cookies(self.driver)
                    except Exception as e:
                        logger.debug(f"登录后重新打开问题页失败: {e}")

                try:
                    self._persist_cookies(self.driver)
                except Exception as e:
                    logger.debug(f"结束前持久化cookies失败: {e}")
                return all_items
        except Exception as e:
            logger.error(f"浏览器抓取失败: {e}")
            return []
        finally:
            try:
                self._persist_cookies(self.driver)
            except Exception as e:
                logger.debug(f"结束兜底持久化cookies失败: {e}")
            if not self.headless:
                try:
                    # 检查是否在交互式环境中
                    import sys
                    if sys.stdin.isatty():
                        input("👀 非无头模式，按回车键关闭浏览器窗口...")
                    else:
                        logger.info("非交互式环境，自动关闭浏览器窗口")
                        time.sleep(2)  # 给用户一点时间看到浏览器内容
                except (EOFError, KeyboardInterrupt):
                    logger.info("标准输入不可用或用户中断，直接关闭浏览器。")
            self.close()

    @staticmethod
    def save_feeds_data(feeds_data: list, filename: str) -> bool:
        try:
            # 自动创建输出目录
            try:
                p = Path(filename)
                if p.parent and str(p.parent) not in ("", "."):
                    p.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.debug(f"创建输出目录失败（将继续尝试保存文件）: {e}")
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(feeds_data, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ 浏览器抓取feeds数据已保存到: {filename}")
            return True
        except Exception as e:
            logger.error(f"保存feeds数据失败: {e}")
            return False

    def extract_answers_from_feeds(self, feeds_data: List[Dict]) -> List[Dict]:
        """从feeds数据中提取答案（browser模式辅助）"""
        answers = []
        for feed_item in feeds_data:
            try:
                if feed_item.get('target_type') != 'answer':
                    continue
                target = feed_item.get('target', {})
                if not target:
                    continue
                answer_info = {
                    'answer_id': str(target.get('id', '')),
                    'content': target.get('content', ''),
                    'excerpt': target.get('excerpt', ''),
                    'voteup_count': target.get('voteup_count', 0),
                    'comment_count': target.get('comment_count', 0),
                    'created_time': target.get('created_time', 0),
                    'updated_time': target.get('updated_time', 0),
                    'author': target.get('author', {}).get('name', ''),
                    'author_url_token': target.get('author', {}).get('url_token', ''),
                    'question_id': target.get('question', {}).get('id', ''),
                    'question_title': target.get('question', {}).get('title', ''),
                    'is_author': target.get('relationship', {}).get('is_author', False)
                }
                answers.append(answer_info)
            except Exception as e:
                logger.warning(f"解析feed项失败: {e}")
                continue
        logger.info(f"📝 从feeds中提取到 {len(answers)} 个答案")
        return answers


def main():
    """主测试函数"""
    parser = argparse.ArgumentParser(description="知乎feeds懒加载爬虫")
    parser.add_argument("--mode", choices=["requests", "browser"], default="requests", help="抓取模式：requests 或 browser")
    parser.add_argument("--question-id", dest="question_id", default="19551593", help="问题ID，例如 19551593")
    parser.add_argument("--max-feeds", dest="max_feeds", type=int, default=50, help="requests模式下最大抓取feed数量")
    parser.add_argument("--headless", dest="headless", type=str, choices=["true", "false"], help="browser模式是否无头，默认取config")
    parser.add_argument("--max-scrolls", dest="max_scrolls", type=int, default=30, help="browser模式最大滚动次数")
    parser.add_argument("--pause", dest="pause", type=float, default=2.0, help="browser模式每次滚动后的等待秒数")
    parser.add_argument("--out", dest="out", default=None, help="输出文件路径，不指定则自动生成到output目录")
    args = parser.parse_args()

    logger.info("🚀 知乎API懒加载测试")

    # 确保目录
    try:
        ZhihuConfig.create_directories()
    except Exception:
        pass

    if args.mode == "browser":
        # 方案A：浏览器上下文 + CDP 抓取
        headless = None
        if args.headless is not None:
            headless = (args.headless.lower() == "true")
        crawler = BrowserFeedsCrawler(headless=headless)
        feeds = crawler.crawl_feeds_via_browser(
            question_id=args.question_id,
            max_scrolls=args.max_scrolls,
            pause=args.pause,
            stop_when_is_end=True
        )
        # 处理输出路径：如果是目录则自动生成文件名
        if args.out:
            out_path = Path(args.out)
            if out_path.is_dir() or str(out_path).endswith('/'):
                out_path = out_path / f"feeds_{args.question_id}_browser.json"
            out_path = str(out_path)
        else:
            out_path = f"{ZhihuConfig.OUTPUT_DIR}/feeds_{args.question_id}_browser.json"
        try:
            crawler.save_feeds_data(feeds, out_path)
            logger.info(f"🎉 Browser模式完成，items={len(feeds)}，输出: {out_path}")
        except Exception as e:
            logger.error(f"保存Browser模式feeds失败: {e}")
        # 提取答案示例
        answers = crawler.extract_answers_from_feeds(feeds)
        logger.info(f"📝 提取答案数: {len(answers)}")
        return

    # 默认：requests 模式，沿用原有测试流程
    crawler = ZhihuLazyLoadCrawler()

    # 测试懒加载能力
    logger.info("\n" + "="*60)
    logger.info("🧪 懒加载能力测试")
    logger.info("="*60)

    ability_result = crawler.test_lazyload_ability(args.question_id)

    if not ability_result['success']:
        logger.error(f"❌ 测试失败: {ability_result.get('error')}")
        return

    if ability_result['lazyload_supported']:
        logger.info("✅ 知乎支持懒加载！")

        if ability_result['continuous_request_supported']:
            logger.info("✅ 支持连续请求fetch文件！")

            # 执行完整懒加载测试
            logger.info("\n" + "="*60)
            logger.info("🚀 执行完整懒加载爬取")
            logger.info("="*60)

            all_feeds = crawler.crawl_all_feeds_lazyload(args.question_id, max_feeds=args.max_feeds)

            if all_feeds:
                # 提取答案
                answers = crawler.extract_answers_from_feeds(all_feeds)

                # 保存数据
                out_path = args.out or f"{ZhihuConfig.OUTPUT_DIR}/feeds_{args.question_id}_requests.json"
                crawler.save_feeds_data(all_feeds, out_path)

                logger.info("🎉 懒加载测试成功!")
                logger.info(f"📊 总feeds数: {len(all_feeds)}")
                logger.info(f"📝 提取答案数: {len(answers)}")

                if answers:
                    logger.info("📋 示例答案信息:")
                    for i, answer in enumerate(answers[:3], 1):
                        logger.info(f"  答案{i}: {answer['author']} - {answer['voteup_count']}赞")
            else:
                logger.warning("⚠️ 未获取到feeds数据")

        else:
            logger.warning("⚠️ 不支持连续请求，可能存在问题")

    else:
        logger.warning("⚠️ 不支持懒加载或已到达数据末尾")


if __name__ == "__main__":
    main()
