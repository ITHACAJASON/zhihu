#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速验证工具 - 测试反爬解决方案效果
"""

import requests
import json
import time
from pathlib import Path
from loguru import logger

class QuickTester:
    """快速测试工具"""

    def __init__(self):
        self.session = requests.Session()
        self.load_cookies()

        # 设置基础headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        })

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
                logger.info(f"✅ 加载cookies成功: {len(cookies_data)}个")
                return True
        except Exception as e:
            logger.error(f"❌ 加载cookies失败: {e}")
            return False

    def test_basic_connectivity(self):
        """测试基础连接性"""
        logger.info("🔍 测试基础连接性...")

        try:
            # 测试主页访问
            response = self.session.get('https://www.zhihu.com', timeout=10)
            logger.info(f"🏠 主页访问状态: {response.status_code}")

            # 测试问题页面访问
            response = self.session.get('https://www.zhihu.com/question/354793553', timeout=10)
            logger.info(f"❓ 问题页面访问状态: {response.status_code}")

            return True
        except Exception as e:
            logger.error(f"❌ 连接测试失败: {e}")
            return False

    def test_api_status(self, question_id="25038841"):
        """测试API状态"""
        logger.info(f"🔍 测试API状态 (问题ID: {question_id})...")

        try:
            # 构建feeds API URL
            feeds_url = f"https://www.zhihu.com/api/v4/questions/{question_id}/feeds"

            params = {
                'include': 'data[*].is_normal,admin_closed_comment,reward_info,is_collapsed,annotation_action,annotation_detail,collapse_reason,is_sticky,collapsed_by,suggest_edit,comment_count,can_comment,content,editable_content,attachment,voteup_count,reshipment_settings,comment_permission,created_time,updated_time,review_info,relevant_info,question,excerpt,is_labeled,paid_info,paid_info_content,reaction_instruction,relationship.is_authorized,is_authorized,is_author,voting,is_thanked,is_nothelp;data[*].author.follower_count,vip_info,kvip_info,badge[*].topics;data[*].settings.table_of_content.enabled',
                'limit': '5',
                'order': 'default',
                'ws_qiangzhisafe': '0',
                'platform': 'desktop',
                'offset': '',
                'session_id': str(int(time.time() * 1000000))
            }

            # 设置headers
            headers = {
                'Referer': f'https://www.zhihu.com/question/{question_id}',
                'X-Requested-With': 'fetch'
            }

            response = self.session.get(feeds_url, params=params, headers=headers, timeout=15)

            logger.info(f"📡 API响应状态码: {response.status_code}")

            if response.status_code == 200:
                data = response.json()

                # 分析响应数据
                feeds_count = len(data.get('data', []))
                session_info = data.get('session', {})
                session_id = session_info.get('id', '')
                paging = data.get('paging', {})

                logger.info(f"📦 Feeds数量: {feeds_count}")
                logger.info(f"🔑 Session ID: '{session_id}'")
                logger.info(f"📄 分页信息: is_end={paging.get('is_end', 'Unknown')}")

                # 判断状态
                if feeds_count > 0 and session_id:
                    logger.info("✅ API状态: 正常")
                    return {'status': 'success', 'feeds': feeds_count, 'session_id': session_id}
                elif feeds_count == 0 and session_id == '':
                    logger.info("⚠️ API状态: 返回空数据 (可能需要验证)")
                    return {'status': 'empty_data', 'feeds': feeds_count, 'session_id': session_id}
                else:
                    logger.info("❌ API状态: 数据不完整")
                    return {'status': 'incomplete', 'feeds': feeds_count, 'session_id': session_id}

            elif response.status_code == 403:
                logger.info("🚫 API状态: 403 Forbidden (需要验证)")
                return {'status': 'forbidden', 'error': '需要验证'}
            else:
                logger.info(f"❌ API状态: HTTP {response.status_code}")
                return {'status': 'error', 'code': response.status_code}

        except Exception as e:
            logger.error(f"❌ API测试失败: {e}")
            return {'status': 'exception', 'error': str(e)}

    def test_lazyload_pagination(self, question_id="25038841"):
        """测试懒加载分页"""
        logger.info(f"🔍 测试懒加载分页 (问题ID: {question_id})...")

        try:
            # 第一次请求
            feeds_url = f"https://www.zhihu.com/api/v4/questions/{question_id}/feeds"

            params = {
                'include': 'data[*].is_normal,admin_closed_comment,reward_info,is_collapsed,annotation_action,annotation_detail,collapse_reason,is_sticky,collapsed_by,suggest_edit,comment_count,can_comment,content,editable_content,attachment,voteup_count,reshipment_settings,comment_permission,created_time,updated_time,review_info,relevant_info,question,excerpt,is_labeled,paid_info,paid_info_content,reaction_instruction,relationship.is_authorized,is_authorized,is_author,voting,is_thanked,is_nothelp;data[*].author.follower_count,vip_info,kvip_info,badge[*].topics;data[*].settings.table_of_content.enabled',
                'limit': '3',
                'order': 'default',
                'ws_qiangzhisafe': '0',
                'platform': 'desktop',
                'offset': '',
                'session_id': str(int(time.time() * 1000000))
            }

            headers = {
                'Referer': f'https://www.zhihu.com/question/{question_id}',
                'X-Requested-With': 'fetch'
            }

            response = self.session.get(feeds_url, params=params, headers=headers, timeout=15)

            if response.status_code == 200:
                data = response.json()
                paging = data.get('paging', {})

                if 'next' in paging and paging.get('next'):
                    logger.info("✅ 分页支持: 有下一页URL")

                    # 测试下一页
                    next_url = paging['next']
                    logger.info(f"🔗 下一页URL: {next_url[:100]}...")

                    # 简单测试下一页是否可访问
                    next_response = self.session.get(next_url, headers=headers, timeout=15)
                    if next_response.status_code == 200:
                        logger.info("✅ 下一页可访问")
                        return {'pagination': True, 'next_page': True}
                    else:
                        logger.info(f"❌ 下一页访问失败: {next_response.status_code}")
                        return {'pagination': True, 'next_page': False}
                else:
                    logger.info("⚠️ 分页支持: 无下一页URL")
                    return {'pagination': False, 'next_page': False}
            else:
                logger.error(f"❌ 分页测试失败: HTTP {response.status_code}")
                return {'pagination': False, 'next_page': False}

        except Exception as e:
            logger.error(f"❌ 分页测试异常: {e}")
            return {'pagination': False, 'next_page': False}

    def comprehensive_test(self):
        """综合测试"""
        logger.info("🚀 开始综合测试...")
        logger.info("=" * 60)

        results = {}

        # 1. 测试基础连接性
        logger.info("\n📡 阶段1: 基础连接性测试")
        results['connectivity'] = self.test_basic_connectivity()

        # 2. 测试API状态
        logger.info("\n📡 阶段2: API状态测试")
        results['api_status'] = self.test_api_status()

        # 3. 测试懒加载分页
        logger.info("\n📡 阶段3: 懒加载分页测试")
        results['pagination'] = self.test_lazyload_pagination()

        # 总结报告
        logger.info("\n" + "=" * 60)
        logger.info("📊 测试总结报告")
        logger.info("=" * 60)

        # 连接性
        if results['connectivity']:
            logger.info("✅ 基础连接: 正常")
        else:
            logger.info("❌ 基础连接: 异常")

        # API状态
        api_result = results['api_status']
        if api_result['status'] == 'success':
            logger.info("✅ API状态: 正常工作")
            logger.info(f"   📦 Feeds数量: {api_result['feeds']}")
            logger.info(f"   🔑 Session ID: {api_result['session_id'][:20]}...")
        elif api_result['status'] == 'empty_data':
            logger.info("⚠️ API状态: 返回空数据（可能需要验证）")
        elif api_result['status'] == 'forbidden':
            logger.info("🚫 API状态: 403 Forbidden（需要验证）")
        else:
            logger.info(f"❌ API状态: {api_result['status']}")

        # 分页能力
        pagination = results['pagination']
        if pagination['pagination']:
            logger.info("✅ 分页支持: 有")
            if pagination['next_page']:
                logger.info("✅ 下一页访问: 正常")
            else:
                logger.info("❌ 下一页访问: 失败")
        else:
            logger.info("⚠️ 分页支持: 无")

        # 总体评估
        logger.info("\n🎯 总体评估:")

        if (results['connectivity'] and
            api_result['status'] == 'success' and
            pagination['pagination'] and pagination['next_page']):
            logger.info("🎉 状态: 完美！所有功能正常")
            return True
        elif results['connectivity'] and api_result['status'] == 'empty_data':
            logger.info("⚠️ 状态: 需要验证（推荐方案A）")
            return False
        elif api_result['status'] == 'forbidden':
            logger.info("🚫 状态: 被反爬限制（推荐方案A或B）")
            return False
        else:
            logger.info("❌ 状态: 存在问题，需要进一步诊断")
            return False

    def save_test_report(self, results):
        """保存测试报告"""
        report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'test_results': results,
            'recommendations': []
        }

        if not results.get('connectivity', False):
            report['recommendations'].append("检查网络连接")

        api_status = results.get('api_status', {})
        if api_status.get('status') == 'forbidden':
            report['recommendations'].extend([
                "执行用户验证（方案A）",
                "考虑更换网络环境（方案B）"
            ])
        elif api_status.get('status') == 'empty_data':
            report['recommendations'].extend([
                "执行用户验证（方案A）",
                "检查cookies是否过期"
            ])

        pagination = results.get('pagination', {})
        if not pagination.get('pagination', False):
            report['recommendations'].append("检查懒加载实现")

        # 保存报告
        with open('quick_test_report.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info("✅ 测试报告已保存: quick_test_report.json")


def main():
    """主函数"""
    logger.info("🔬 知乎反爬虫快速测试工具")
    logger.info("=" * 60)

    tester = QuickTester()
    success = tester.comprehensive_test()

    # 保存报告
    tester.save_test_report({
        'connectivity': tester.test_basic_connectivity(),
        'api_status': tester.test_api_status(),
        'pagination': tester.test_lazyload_pagination()
    })

    logger.info("\n" + "=" * 60)
    if success:
        logger.info("🎉 测试完成！API工作正常")
    else:
        logger.info("⚠️ 测试完成，发现问题需要解决")
        logger.info("\n📋 建议下一步:")
        logger.info("1. 运行: python3 resolve_verification.py")
        logger.info("2. 或查看: anticrawl_solution_guide.md")


if __name__ == "__main__":
    main()
