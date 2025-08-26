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
from typing import List, Dict, Optional, Tuple
from loguru import logger
from pathlib import Path

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
        """从feeds数据中提取答案"""
        answers = []

        for feed_item in feeds_data:
            try:
                # 检查是否是答案类型
                if feed_item.get('target_type') != 'answer':
                    continue

                # 提取答案数据
                target = feed_item.get('target', {})
                if not target:
                    continue

                # 构建答案信息
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
        """测试懒加载能力"""
        logger.info(f"🧪 测试问题 {question_id} 的懒加载能力")

        # 第一页测试
        first_page = self.fetch_feeds_page(question_id, limit=5)
        if not first_page:
            return {'success': False, 'error': '无法获取第一页数据'}

        # 分析分页信息
        paging = first_page.get('paging', {})
        has_paging = bool(paging)
        has_next = bool(paging.get('next'))
        is_end = paging.get('is_end', True)

        # 测试下一页
        next_page_success = False
        if not is_end and has_next:
            next_params = self.parse_next_url(paging['next'])
            cursor = next_params.get('cursor')
            offset = next_params.get('offset')

            if cursor or offset:
                next_page = self.fetch_feeds_page(question_id, cursor=cursor,
                                                offset=int(offset) if offset else None, limit=5)
                next_page_success = bool(next_page)

        # 分析结果
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

    def save_feeds_data(self, feeds_data: List[Dict], filename: str):
        """保存feeds数据到文件"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(feeds_data, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ feeds数据已保存到: {filename}")
            return True
        except Exception as e:
            logger.error(f"保存feeds数据失败: {e}")
            return False


def main():
    """主测试函数"""
    logger.info("🚀 知乎API懒加载测试")

    crawler = ZhihuLazyLoadCrawler()

    # 测试问题ID - 使用一个答案较多的问题
    test_question_id = "19551593"  # 这个问题应该有更多答案

    # 测试懒加载能力
    logger.info("\n" + "="*60)
    logger.info("🧪 懒加载能力测试")
    logger.info("="*60)

    ability_result = crawler.test_lazyload_ability(test_question_id)

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

            all_feeds = crawler.crawl_all_feeds_lazyload(test_question_id, max_feeds=50)

            if all_feeds:
                # 提取答案
                answers = crawler.extract_answers_from_feeds(all_feeds)

                # 保存数据
                crawler.save_feeds_data(all_feeds, 'lazyload_feeds_test.json')

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
