#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知乎API修复版本
解决返回空数据和空session ID的问题
"""

import json
import requests
import time
import re
from pathlib import Path
from loguru import logger
from typing import Dict, List, Optional

class ZhihuAPIFixer:
    """知乎API修复器"""
    
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

    def check_login_status(self):
        """检查登录状态"""
        try:
            # 访问用户API检查登录状态
            check_url = "https://www.zhihu.com/api/v4/me"
            response = self.session.get(check_url, timeout=10)
            
            if response.status_code == 200:
                user_data = response.json()
                if 'id' in user_data:
                    logger.info(f"✅ 登录状态正常，用户: {user_data.get('name', 'Unknown')}")
                    return True
            
            logger.warning("❌ 登录状态异常")
            return False
            
        except Exception as e:
            logger.error(f"检查登录状态失败: {e}")
            return False

    def get_question_basic_info(self, question_id):
        """获取问题基本信息"""
        try:
            question_url = f"https://www.zhihu.com/api/v4/questions/{question_id}"
            response = self.session.get(question_url, timeout=10)
            
            if response.status_code == 200:
                question_data = response.json()
                logger.info(f"问题标题: {question_data.get('title', 'Unknown')}")
                logger.info(f"答案数量: {question_data.get('answer_count', 0)}")
                logger.info(f"关注数量: {question_data.get('follower_count', 0)}")
                return question_data
            else:
                logger.warning(f"获取问题信息失败: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"获取问题基本信息失败: {e}")
            return None

    def try_answers_api(self, question_id, limit=20, offset=0):
        """尝试使用answers API端点"""
        try:
            answers_url = f"https://www.zhihu.com/api/v4/questions/{question_id}/answers"
            
            params = {
                'include': 'data[*].is_normal,admin_closed_comment,reward_info,is_collapsed,annotation_action,annotation_detail,collapse_reason,is_sticky,collapsed_by,suggest_edit,comment_count,can_comment,content,editable_content,attachment,voteup_count,reshipment_settings,comment_permission,created_time,updated_time,review_info,relevant_info,question,excerpt,is_labeled,paid_info,paid_info_content,reaction_instruction,relationship.is_authorized,is_author,voting,is_thanked,is_nothelp;data[*].author.follower_count,vip_info,kvip_info,badge[*].topics;data[*].settings.table_of_content.enabled',
                'limit': limit,
                'offset': offset,
                'platform': 'desktop',
                'sort_by': 'default'
            }
            
            # 设置referer
            headers = self.base_headers.copy()
            headers['Referer'] = f'https://www.zhihu.com/question/{question_id}'
            
            response = self.session.get(answers_url, params=params, headers=headers, timeout=30)
            
            logger.info(f"Answers API状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                answers_count = len(data.get('data', []))
                logger.info(f"📊 通过answers API获取到 {answers_count} 个答案")
                
                if answers_count > 0:
                    # 保存成功响应
                    with open('api_answers_success.json', 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    return data
                else:
                    logger.warning("answers API返回空数据")
                    return data
            else:
                logger.error(f"Answers API失败: {response.status_code}")
                logger.error(f"响应内容: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Answers API请求失败: {e}")
            return None

    def try_feeds_api_enhanced(self, question_id, limit=20):
        """增强版feeds API尝试"""
        try:
            # 先访问问题页面建立上下文
            question_page_url = f"https://www.zhihu.com/question/{question_id}"
            page_response = self.session.get(question_page_url, timeout=10)
            
            if page_response.status_code != 200:
                logger.warning(f"无法访问问题页面: {page_response.status_code}")
                return None
            
            # 从页面提取必要信息
            html_content = page_response.text
            
            # 查找csrf token
            csrf_match = re.search(r'"_xsrf":"([^"]*)"', html_content)
            if csrf_match:
                csrf_token = csrf_match.group(1)
                logger.info(f"提取到CSRF token: {csrf_token[:10]}...")
            
            # 构建feeds API请求
            feeds_url = f"https://www.zhihu.com/api/v4/questions/{question_id}/feeds"
            
            params = {
                'include': 'data[*].is_normal,admin_closed_comment,reward_info,is_collapsed,annotation_action,annotation_detail,collapse_reason,is_sticky,collapsed_by,suggest_edit,comment_count,can_comment,content,editable_content,attachment,voteup_count,reshipment_settings,comment_permission,created_time,updated_time,review_info,relevant_info,question,excerpt,is_labeled,paid_info,paid_info_content,reaction_instruction,relationship.is_authorized,is_author,voting,is_thanked,is_nothelp;data[*].author.follower_count,vip_info,kvip_info,badge[*].topics;data[*].settings.table_of_content.enabled',
                'limit': limit,
                'order': 'default',
                'platform': 'desktop',
                'ws_qiangzhisafe': '0'
            }
            
            # 不设置offset，让API自动处理
            # params['offset'] = ''  # 空字符串
            
            headers = self.base_headers.copy()
            headers['Referer'] = question_page_url
            headers['X-Requested-With'] = 'fetch'
            
            response = self.session.get(feeds_url, params=params, headers=headers, timeout=30)
            
            logger.info(f"Enhanced Feeds API状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                feeds_count = len(data.get('data', []))
                session_id = data.get('session', {}).get('id', '')
                
                logger.info(f"📊 通过enhanced feeds API获取到 {feeds_count} 个内容")
                logger.info(f"🔑 Session ID: {session_id or '空'}")
                
                if feeds_count > 0 or session_id:
                    # 保存响应
                    with open('api_feeds_enhanced_success.json', 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    return data
                else:
                    logger.warning("enhanced feeds API返回空数据且无session")
                    return data
            else:
                logger.error(f"Enhanced Feeds API失败: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Enhanced Feeds API请求失败: {e}")
            return None

    def comprehensive_test(self, question_ids):
        """综合测试多个问题"""
        results = {}
        
        # 首先检查登录状态
        if not self.check_login_status():
            logger.error("❌ 登录状态异常，请重新获取cookies")
            return results
        
        for question_id in question_ids:
            logger.info(f"\n{'='*60}")
            logger.info(f"🔍 测试问题ID: {question_id}")
            logger.info(f"{'='*60}")
            
            result = {
                'question_id': question_id,
                'basic_info': None,
                'answers_api': None,
                'feeds_api': None,
                'success': False
            }
            
            # 1. 获取问题基本信息
            basic_info = self.get_question_basic_info(question_id)
            result['basic_info'] = basic_info
            
            if basic_info:
                answer_count = basic_info.get('answer_count', 0)
                if answer_count == 0:
                    logger.warning(f"⚠️ 问题 {question_id} 本身没有答案")
                    result['no_answers'] = True
                else:
                    logger.info(f"📝 问题有 {answer_count} 个答案，继续测试API")
            
            # 2. 尝试answers API
            logger.info("🎯 尝试answers API...")
            answers_result = self.try_answers_api(question_id, limit=5)
            result['answers_api'] = answers_result
            
            if answers_result and answers_result.get('data'):
                logger.info(f"✅ Answers API成功获取数据")
                result['success'] = True
            
            # 3. 尝试enhanced feeds API
            logger.info("🎯 尝试enhanced feeds API...")
            feeds_result = self.try_feeds_api_enhanced(question_id, limit=5)
            result['feeds_api'] = feeds_result
            
            if feeds_result and (feeds_result.get('data') or feeds_result.get('session', {}).get('id')):
                logger.info(f"✅ Enhanced Feeds API成功")
                result['success'] = True
            
            results[question_id] = result
            
            # 延时避免请求过快
            time.sleep(2)
        
        return results

    def generate_report(self, results):
        """生成测试报告"""
        report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_questions': len(results),
            'successful_questions': sum(1 for r in results.values() if r['success']),
            'failed_questions': [],
            'successful_questions_list': [],
            'summary': {},
            'recommendations': []
        }
        
        for question_id, result in results.items():
            if result['success']:
                report['successful_questions_list'].append({
                    'question_id': question_id,
                    'title': result.get('basic_info', {}).get('title', 'Unknown'),
                    'answer_count': result.get('basic_info', {}).get('answer_count', 0),
                    'working_apis': []
                })
                
                # 记录工作的API
                if result.get('answers_api') and result['answers_api'].get('data'):
                    report['successful_questions_list'][-1]['working_apis'].append('answers')
                if result.get('feeds_api') and (result['feeds_api'].get('data') or result['feeds_api'].get('session', {}).get('id')):
                    report['successful_questions_list'][-1]['working_apis'].append('feeds')
            else:
                report['failed_questions'].append({
                    'question_id': question_id,
                    'reason': 'API调用失败或返回空数据'
                })
        
        # 生成建议
        if report['successful_questions'] > 0:
            report['recommendations'].append("✅ 发现可工作的API端点，建议使用成功的方法")
        else:
            report['recommendations'].extend([
                "❌ 所有API测试失败，建议：",
                "1. 重新获取完整的登录cookies",
                "2. 检查网络环境和反爬限制",
                "3. 考虑使用Selenium备选方案"
            ])
        
        # 保存报告
        with open('api_test_report.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        return report


def main():
    """主测试函数"""
    logger.info("🚀 启动知乎API修复测试")
    
    fixer = ZhihuAPIFixer()
    
    # 测试问题列表 - 包含不同类型的问题
    test_questions = [
        "354793553",  # 你提到的问题
        "25038841",   # 经典编程问题
        "19551593",   # 另一个测试问题
    ]
    
    # 执行综合测试
    results = fixer.comprehensive_test(test_questions)
    
    # 生成报告
    report = fixer.generate_report(results)
    
    # 输出总结
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 测试完成总结")
    logger.info(f"{'='*60}")
    logger.info(f"总测试问题数: {report['total_questions']}")
    logger.info(f"成功问题数: {report['successful_questions']}")
    logger.info(f"失败问题数: {len(report['failed_questions'])}")
    
    if report['successful_questions'] > 0:
        logger.info(f"\n✅ 成功的问题:")
        for q in report['successful_questions_list']:
            logger.info(f"  - {q['question_id']}: {q['title'][:50]}... (APIs: {', '.join(q['working_apis'])})")
    
    if report['failed_questions']:
        logger.info(f"\n❌ 失败的问题:")
        for q in report['failed_questions']:
            logger.info(f"  - {q['question_id']}: {q['reason']}")
    
    logger.info(f"\n📋 建议:")
    for rec in report['recommendations']:
        logger.info(f"  {rec}")
    
    logger.info(f"\n📄 详细报告已保存到: api_test_report.json")


if __name__ == "__main__":
    main()

