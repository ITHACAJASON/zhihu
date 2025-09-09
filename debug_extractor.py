#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试参数提取器
"""

import json
import time
from dynamic_params_extractor import DynamicParamsExtractor
from loguru import logger

def debug_extractor():
    """调试参数提取器"""
    logger.info("🔍 开始调试参数提取器")
    
    # 创建提取器实例（非无头模式，便于观察）
    extractor = DynamicParamsExtractor(headless=False)
    
    try:
        # 测试提取参数
        question_id = "30215562"
        logger.info(f"📋 测试问题ID: {question_id}")
        
        # 手动设置驱动
        extractor.driver = extractor._setup_driver()
        logger.info("✅ Chrome驱动创建成功")
        
        # 加载cookies
        logger.info("🍪 加载cookies")
        extractor.driver.get("https://www.zhihu.com")
        
        # 读取并设置cookies
        import json
        try:
            with open('/Users/jasonlai/Documents/Code/Crawler/zhihu/cookies/zhihu_cookies.json', 'r') as f:
                cookies = json.load(f)
            
            for cookie in cookies:
                try:
                    extractor.driver.add_cookie(cookie)
                except Exception as e:
                    logger.debug(f"设置cookie失败: {cookie['name']} - {e}")
                    
            logger.info(f"✅ 成功加载 {len(cookies)} 个cookies")
        except Exception as e:
            logger.warning(f"⚠️ 加载cookies失败: {e}")
        
        # 访问页面
        url = f"https://www.zhihu.com/question/{question_id}"
        logger.info(f"🌐 访问页面: {url}")
        extractor.driver.get(url)
        
        # 等待页面加载
        time.sleep(5)
        logger.info("⏳ 页面加载完成")
        
        # 检查网络日志
        logs = extractor.driver.get_log('performance')
        logger.info(f"📊 获取到 {len(logs)} 条网络日志")
        
        # 分析日志
        feeds_requests = []
        api_requests = []
        for i, log in enumerate(logs):
            try:
                message = json.loads(log['message'])
                if message.get('message', {}).get('method') == 'Network.requestWillBeSent':
                    request = message['message']['params']['request']
                    url_log = request.get('url', '')
                    
                    # 记录所有API请求
                    if '/api/' in url_log:
                        api_requests.append(url_log)
                        logger.debug(f"🔍 API请求: {url_log}")
                    
                    if '/api/v4/questions/' in url_log and '/feeds' in url_log:
                        feeds_requests.append({
                            'url': url_log,
                            'headers': request.get('headers', {})
                        })
                        logger.info(f"🎯 发现feeds请求: {url_log}")
            except Exception as e:
                continue
                
        logger.info(f"🔍 总共发现 {len(api_requests)} 个API请求")
        for api_url in api_requests[:10]:  # 只显示前10个
            logger.info(f"   - {api_url}")
                
        logger.info(f"📈 找到 {len(feeds_requests)} 个feeds请求")
        
        if not feeds_requests:
            logger.warning("⚠️ 未找到feeds请求，尝试模拟用户行为")
            
            # 模拟用户行为 - 多次下滑以触发feeds请求
            logger.info("🎯 开始模拟用户行为...")
            time.sleep(2)
            
            # 多次滚动页面，每次滚动后等待
            logger.info("📜 开始滚动页面以触发feeds请求...")
            for i in range(8):  # 增加滚动次数
                logger.info(f"📜 第 {i+1} 次滚动")
                extractor.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)  # 每次滚动后等待更长时间
                
                # 检查是否有新的feeds请求
                current_logs = extractor.driver.get_log('performance')
                for log in current_logs:
                    try:
                        message = json.loads(log['message'])
                        if message.get('message', {}).get('method') == 'Network.requestWillBeSent':
                            request = message['message']['params']['request']
                            url_log = request.get('url', '')
                            if '/feeds' in url_log:
                                logger.info(f"🎯 发现feeds请求: {url_log}")
                    except Exception as e:
                        continue
            
            logger.info("📜 滚动完成，等待最终加载...")
            time.sleep(3)
            
            # 获取所有网络日志
            all_logs = extractor.driver.get_log('performance')
            logger.info(f"📊 总共获取到 {len(all_logs)} 条网络日志")
            
            # 分析网络日志
            feeds_requests_new = []
            for log in all_logs:
                try:
                    message = json.loads(log['message'])
                    if message.get('message', {}).get('method') == 'Network.requestWillBeSent':
                        request = message['message']['params']['request']
                        url_log = request.get('url', '')
                        
                        # 记录所有API请求
                        if '/api/' in url_log:
                            api_requests.append(url_log)
                            logger.debug(f"🔍 新API请求: {url_log}")
                        
                        if '/api/v4/questions/' in url_log and '/feeds' in url_log:
                            feeds_requests_new.append({
                                'url': url_log,
                                'headers': request.get('headers', {})
                            })
                            logger.info(f"🎯 发现feeds请求: {url_log}")
                except Exception as e:
                    continue
            
            feeds_requests.extend(feeds_requests_new)
            logger.info(f"🔍 模拟行为后总共发现 {len(feeds_requests_new)} 个新feeds请求")
            
            # 手动控制权交还
            logger.info("\n=== 🎮 手动控制模式 ===")
            logger.info("浏览器已打开，请在浏览器中完成以下操作：")
            logger.info("1. 如果需要登录，请完成登录")
            logger.info("2. 继续滚动页面直到看到feeds请求")
            logger.info("3. 完成后在此控制台输入 'done' 并按回车继续")
            
            while True:
                user_input = input("请输入 'done' 继续: ").strip().lower()
                if user_input == 'done':
                    break
                else:
                    logger.info("请输入 'done' 继续...")
            
            # 用户操作完成后，重新获取网络日志
            logger.info("🔄 用户操作完成，重新分析网络日志...")
            final_logs = extractor.driver.get_log('performance')
            logger.info(f"📊 最终获取到 {len(final_logs)} 条网络日志")
            
            # 重新分析所有feeds请求
            feeds_requests = []  # 重置feeds请求列表
            api_requests = []
            
            for log in final_logs:
                try:
                    message = json.loads(log['message'])
                    if message.get('message', {}).get('method') == 'Network.requestWillBeSent':
                        request = message['message']['params']['request']
                        url_log = request.get('url', '')
                        
                        if '/api/' in url_log:
                            api_requests.append(url_log)
                        
                        if '/api/v4/questions/' in url_log and '/feeds' in url_log:
                            feeds_requests.append({
                                'url': url_log,
                                'headers': request.get('headers', {})
                            })
                            logger.info(f"🎯 发现feeds请求: {url_log}")
                except Exception as e:
                    continue
            
            logger.info(f"🔍 最终发现 {len(api_requests)} 个API请求")
            logger.info(f"🎯 最终发现 {len(feeds_requests)} 个feeds请求")
                     
         # 分析找到的请求
        for i, req in enumerate(feeds_requests):
            logger.info(f"📋 请求 {i+1}:")
            logger.info(f"   URL: {req['url']}")
            headers = req['headers']
            logger.info(f"   x-zse-96: {headers.get('x-zse-96', 'N/A')}")
            logger.info(f"   x-zst-81: {headers.get('x-zst-81', 'N/A')}")
            logger.info(f"   cookie: {headers.get('cookie', 'N/A')[:100]}...")
            
        # 尝试提取参数
        params = extractor._extract_params_from_logs()
        if params:
            logger.info(f"✅ 成功提取参数: {params}")
        else:
            logger.warning("❌ 参数提取失败")
            
    except Exception as e:
        logger.error(f"❌ 调试过程出错: {e}")
        
    finally:
        if extractor.driver:
            # 保持浏览器打开一段时间，便于观察
            logger.info("🔍 浏览器将保持打开30秒，便于观察...")
            time.sleep(30)
            extractor.close()
            
if __name__ == "__main__":
    debug_extractor()