#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复知乎API session获取问题
解决返回空数据和空session ID的问题
"""

import json
import requests
import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from loguru import logger

class ZhihuAPISessionFixer:
    """修复知乎API Session问题"""
    
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en,zh-CN;q=0.9,zh;q=0.8,de;q=0.7,zh-TW;q=0.6',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'DNT': '1',
            'Priority': 'u=1, i',
            'Referer': 'https://www.zhihu.com/',
            'Sec-Ch-Ua': '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"macOS"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'X-Requested-With': 'fetch'
        }
        self.session.headers.update(self.headers)
        self.load_cookies()

    def load_cookies(self):
        """加载cookies"""
        try:
            with open('cookies/zhihu_cookies.json', 'r', encoding='utf-8') as f:
                cookies_data = json.load(f)
                for cookie in cookies_data:
                    self.session.cookies.set(
                        cookie['name'], 
                        cookie['value'], 
                        domain=cookie.get('domain', '.zhihu.com'),
                        path=cookie.get('path', '/'),
                        secure=cookie.get('secure', False)
                    )
                logger.info(f"成功加载cookies，共{len(cookies_data)}个")
        except Exception as e:
            logger.error(f"加载cookies失败: {e}")

    def extract_session_from_page(self, question_id):
        """从问题页面提取有效的session信息"""
        try:
            question_url = f"https://www.zhihu.com/question/{question_id}"
            
            # 访问问题页面
            response = self.session.get(question_url, timeout=30)
            if response.status_code != 200:
                logger.error(f"访问问题页面失败: {response.status_code}")
                return None, None
            
            html_content = response.text
            
            # 方法1: 从页面HTML中提取preload数据
            session_id = None
            preload_data = None
            
            # 查找页面中的session信息
            session_pattern = r'"session_id":"([^"]*)"'
            session_match = re.search(session_pattern, html_content)
            if session_match:
                session_id = session_match.group(1)
                logger.info(f"从页面提取到session_id: {session_id}")
            
            # 查找preload数据
            preload_pattern = r'<script id="js-initialData" type="text/json">(.*?)</script>'
            preload_match = re.search(preload_pattern, html_content, re.DOTALL)
            if preload_match:
                try:
                    preload_json = preload_match.group(1)
                    preload_data = json.loads(preload_json)
                    logger.info("成功提取preload数据")
                except json.JSONDecodeError as e:
                    logger.warning(f"解析preload数据失败: {e}")
            
            # 方法2: 从网络请求中获取session信息
            if not session_id:
                session_id = self.generate_session_id_from_cookies()
            
            return session_id, preload_data
            
        except Exception as e:
            logger.error(f"提取session信息失败: {e}")
            return None, None

    def generate_session_id_from_cookies(self):
        """基于cookies生成session ID"""
        try:
            # 获取d_c0 cookie作为基础
            d_c0 = None
            for cookie in self.session.cookies:
                if cookie.name == 'd_c0':
                    d_c0 = cookie.value
                    break
            
            if d_c0:
                # 使用d_c0和当前时间戳组合生成session_id
                timestamp = str(int(time.time() * 1000))
                # 简化版本：使用时间戳的一部分
                session_id = timestamp + str(abs(hash(d_c0)) % 1000000)
                logger.info(f"基于cookies生成session_id: {session_id}")
                return session_id
            else:
                # 降级到时间戳
                session_id = str(int(time.time() * 1000000))
                logger.warning(f"降级使用时间戳session_id: {session_id}")
                return session_id
                
        except Exception as e:
            logger.error(f"生成session_id失败: {e}")
            return str(int(time.time() * 1000000))

    def test_feeds_api_with_session(self, question_id, session_id=None, limit=3):
        """使用正确的session测试feeds API"""
        try:
            # 如果没有提供session_id，先获取
            if not session_id:
                session_id, preload_data = self.extract_session_from_page(question_id)
            
            # 构建feeds API URL
            feeds_url = f"https://www.zhihu.com/api/v4/questions/{question_id}/feeds"
            
            # API参数
            params = {
                'include': 'data[*].is_normal,admin_closed_comment,reward_info,is_collapsed,annotation_action,annotation_detail,collapse_reason,is_sticky,collapsed_by,suggest_edit,comment_count,can_comment,content,editable_content,attachment,voteup_count,reshipment_settings,comment_permission,created_time,updated_time,review_info,relevant_info,question,excerpt,is_labeled,paid_info,paid_info_content,reaction_instruction,relationship.is_authorized,is_author,voting,is_thanked,is_nothelp;data[*].author.follower_count,vip_info,kvip_info,badge[*].topics;data[*].settings.table_of_content.enabled',
                'offset': '',  # 重要：初始请求使用空字符串
                'limit': str(limit),
                'order': 'default',
                'ws_qiangzhisafe': '0',
                'platform': 'desktop'
            }
            
            # 添加session_id
            if session_id:
                params['session_id'] = session_id
            
            # 设置正确的referer
            headers = self.headers.copy()
            headers['Referer'] = f'https://www.zhihu.com/question/{question_id}'
            
            # 发送请求
            response = self.session.get(feeds_url, params=params, headers=headers, timeout=30)
            
            logger.info(f"API请求状态码: {response.status_code}")
            logger.info(f"API请求URL: {response.url}")
            
            if response.status_code == 200:
                data = response.json()
                
                # 保存响应数据
                with open('api_response_fixed.json', 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                # 分析响应
                answers_count = len(data.get('data', []))
                session_info = data.get('session', {})
                paging_info = data.get('paging', {})
                
                logger.info(f"✅ API请求成功")
                logger.info(f"📊 获取到 {answers_count} 个答案")
                logger.info(f"🔑 Session ID: {session_info.get('id', '空')}")
                logger.info(f"📄 分页信息: is_end={paging_info.get('is_end', 'Unknown')}")
                
                if answers_count > 0:
                    logger.info("🎉 成功获取到有效数据！")
                    return True, data
                else:
                    logger.warning("⚠️ 返回数据为空，可能需要进一步调试")
                    return False, data
                    
            else:
                logger.error(f"❌ API请求失败: {response.status_code}")
                logger.error(f"响应内容: {response.text}")
                return False, None
                
        except Exception as e:
            logger.error(f"测试API时发生错误: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return False, None

    def browser_based_session_extraction(self, question_id):
        """使用浏览器方式获取session（备用方案）"""
        try:
            logger.info("尝试使用浏览器方式获取session...")
            
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            
            driver = webdriver.Chrome(options=chrome_options)
            
            try:
                # 访问问题页面
                question_url = f"https://www.zhihu.com/question/{question_id}"
                driver.get(question_url)
                
                # 加载cookies
                for cookie in self.session.cookies:
                    driver.add_cookie({
                        'name': cookie.name,
                        'value': cookie.value,
                        'domain': cookie.domain,
                        'path': cookie.path
                    })
                
                # 刷新页面
                driver.refresh()
                
                # 等待页面加载
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                # 执行JavaScript获取session信息
                session_script = """
                // 尝试从页面全局变量中获取session信息
                var session_id = null;
                
                // 方法1: 检查window对象
                if (window.__INITIAL_STATE__ && window.__INITIAL_STATE__.entities) {
                    console.log('Found __INITIAL_STATE__');
                }
                
                // 方法2: 检查已有的API请求
                if (window.performance) {
                    var entries = window.performance.getEntriesByType('resource');
                    for (var i = 0; i < entries.length; i++) {
                        if (entries[i].name.includes('/feeds') && entries[i].name.includes('session_id=')) {
                            var url = entries[i].name;
                            var match = url.match(/session_id=([^&]*)/);
                            if (match) {
                                session_id = match[1];
                                break;
                            }
                        }
                    }
                }
                
                return {
                    session_id: session_id,
                    current_timestamp: Date.now()
                };
                """
                
                session_info = driver.execute_script(session_script)
                logger.info(f"浏览器提取的session信息: {session_info}")
                
                return session_info.get('session_id')
                
            finally:
                driver.quit()
                
        except Exception as e:
            logger.error(f"浏览器方式获取session失败: {e}")
            return None


def main():
    """主测试函数"""
    logger.info("🚀 开始修复API session问题")
    
    fixer = ZhihuAPISessionFixer()
    
    # 测试问题列表
    test_questions = [
        "354793553",  # 有答案的问题
        "25038841"    # 另一个测试问题
    ]
    
    for question_id in test_questions:
        logger.info(f"\n{'='*50}")
        logger.info(f"🔍 测试问题ID: {question_id}")
        logger.info(f"{'='*50}")
        
        # 方法1: 从页面提取session
        success, data = fixer.test_feeds_api_with_session(question_id)
        
        if not success:
            logger.info("方法1失败，尝试浏览器方式...")
            # 方法2: 使用浏览器获取session
            browser_session = fixer.browser_based_session_extraction(question_id)
            if browser_session:
                logger.info(f"🎯 浏览器获取到session: {browser_session}")
                success, data = fixer.test_feeds_api_with_session(question_id, browser_session)
        
        if success:
            logger.info(f"✅ 问题 {question_id} 测试成功！")
            break
        else:
            logger.warning(f"⚠️ 问题 {question_id} 测试失败")
    
    logger.info("\n🏁 测试完成")

if __name__ == "__main__":
    main()

