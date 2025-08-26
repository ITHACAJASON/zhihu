#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查知乎API cookies有效性
"""

import json
import requests
import os
from datetime import datetime
from loguru import logger
from zhihu_api_encrypt import get_api_headers, extract_d_c0_from_cookies, build_zhihu_api_url

def load_cookies(cookies_path):
    """加载cookies"""
    try:
        if not os.path.exists(cookies_path):
            logger.error(f"Cookies文件不存在: {cookies_path}")
            return None
            
        with open(cookies_path, 'r', encoding='utf-8') as f:
            cookies_data = json.load(f)
            
        logger.info(f"成功加载cookies文件: {cookies_path}")
        logger.info(f"Cookies数量: {len(cookies_data)}")
        
        # 检查cookies过期时间
        for cookie in cookies_data:
            if 'expiry' in cookie:
                expiry_time = datetime.fromtimestamp(cookie['expiry'])
                now = datetime.now()
                if expiry_time > now:
                    logger.info(f"Cookie {cookie['name']} 有效期至: {expiry_time} (未过期)")
                else:
                    logger.warning(f"Cookie {cookie['name']} 已过期: {expiry_time}")
        
        # 转换为requests库可用的格式
        cookies_dict = {}
        for cookie in cookies_data:
            cookies_dict[cookie['name']] = cookie['value']
            
        return cookies_dict
    except Exception as e:
        logger.error(f"加载cookies失败: {e}")
        return None

def test_api_connection(cookies_dict, question_id="25038841"):
    """测试API连接 - 直接使用您提供的答案URL"""
    try:
        logger.info(f"测试API连接，使用问题ID: {question_id}")

        # 直接设置d_c0，不从cookies中提取
        d_c0 = "LhdUv57jkBqPTiH9tVCnp2xbGKAlvES8sWA=|1749179944"
        logger.info(f"使用d_c0: {d_c0}")

        # API路径 - 直接使用feeds端点
        api_path = f"/api/v4/questions/{question_id}/feeds"

        # 参数 - 根据preload信息调整
        params = {
            'include': 'data[*].is_normal,admin_closed_comment,reward_info,is_collapsed,annotation_action,annotation_detail,collapse_reason,is_sticky,collapsed_by,suggest_edit,comment_count,can_comment,content,editable_content,attachment,voteup_count,reshipment_settings,comment_permission,created_time,updated_time,review_info,relevant_info,question,excerpt,is_labeled,paid_info,paid_info_content,reaction_instruction,relationship.is_authorized,is_author,voting,is_thanked,is_nothelp;data[*].author.follower_count,vip_info,kvip_info,badge[*].topics;data[*].settings.table_of_content.enabled',
            'offset': '',
            'limit': '3',
            'order': 'default',
            'ws_qiangzhisafe': '0',
            'platform': 'desktop'
        }
        
        # 构建完整URL
        full_url = build_zhihu_api_url(f"https://www.zhihu.com{api_path}", params)
        
        # 获取加密的请求头
        headers = get_api_headers(api_path, d_c0)

        # 使用浏览器提供的正确值
        headers['X-Zse-93'] = '101_3_3.0'
        headers['X-Zse-96'] = '2.0_wS8D0lCP6oBAj9x4uDSPyLgAMPC0L2UwfHo/ub+SA2K6shtNgmidqur6=JupIeMJ'

        # 添加浏览器特有的请求头
        headers['DNT'] = '1'
        headers['Priority'] = 'u=1, i'

        # 使用浏览器提供的完整cookie字符串
        cookie_str = '_xsrf=3flFJjridUWXsRGeJD7cdpXEdWag6jkQ; _zap=50caaf95-3ccf-4c5a-88b9-009aacf2b626; d_c0=LhdUv57jkBqPTiH9tVCnp2xbGKAlvES8sWA=|1749179944; HMACCOUNT=F9EB196AA549EE10; q_c1=56361d2b4a2f4fe9b798e456f80f6469|1754226619000|1754226619000; Hm_lvt_98beee57fd2ef70ccdd5ca52b9740c49=1754226603; z_c0=2|1:0|10:1755075132|4:z_c0|80:MS4xd3VNQUFBQUFBQUFtQUFBQVlBSlZUYXV0Zkdsbm50TGVYWmhvOG5yenlmNF9YR3pScXJod0NBPT0=|8da7ea89a4932bd80a737e1764568c8f7b4d0a1b5dc2afcfc34602e96abbfc40; edu_user_uuid=edu-v1|9f7f4490-118a-42c5-a431-0790e813acf6; __zse_ck=004_SfbW3Ksv154NLmOVohUo0f7=mH7yErOIBjvhyVKg/G2XBlR=1F9GdLNKCsmCxg/k0WAhkAsASggTaKW23rlsAZ2HtRhbER1uEGxhWq8eOpH2NI9aeJXONWSrhJzcCtNb-swracgijNx8rDHpO9JL3PgP/4R7ytSgvpOQRb0K0nX0AzAQ4wSGkSpo7D3LWZ4r943jmj9GFrhvl1aLVmdwuc//9i9SBynqd1dCVw4nZ6g4ITpbmYdBee4BPJqrvOH2j; SESSIONID=6weJp7oOsUphljzUPyigYeLsYe1RiSeklskebB6BhoN; JOID=UVodB0_RRfyM6DCZQsxW44wr-yxT5jiVxp8G_AGlEYbohF3iHZ5gXOPuO59OpSfOUGqeedRLlmJOQQksifNhNA0=; osd=Ul8RAk_SQPCJ6DOcTslW4Ikn_ixQ4zSQxpwD8ASlEoPkgV3hGJJlXODrN5pOpiLCVWqdfNhOlmFLTQwsivZtMQ0=; tst=r; Hm_lpvt_98beee57fd2ef70ccdd5ca52b9740c49=1756124535; BEC=6c53268835aec2199978cd4b4f988f8c'
        headers['cookie'] = cookie_str
        
        # 添加额外的请求头
        headers['authority'] = 'www.zhihu.com'
        headers['referer'] = f'https://www.zhihu.com/question/{question_id}'
        
        # 首先测试基本的网络连接
        try:
            # 使用headers中的cookie直接请求
            home_headers = {
                'User-Agent': headers['User-Agent'],
                'Accept': headers['Accept'],
                'cookie': headers['cookie']
            }
            response = requests.get("https://www.zhihu.com", headers=home_headers, timeout=10)
            logger.info(f"知乎主页访问状态: {response.status_code}")
            print(f"知乎主页访问状态: {response.status_code}")
        except Exception as e:
            logger.warning(f"知乎主页访问失败: {e}")
            print(f"知乎主页访问失败: {e}")
        
        # 尝试获取答案
        logger.info(f"请求API: {full_url}")
        print(f"请求API: {full_url}")
        print(f"请求头: {json.dumps(headers, indent=2, ensure_ascii=False)}")
        
        # 直接使用requests.get，不需要传入params（已经在URL中）
        response = requests.get(full_url, headers=headers, timeout=30)
        logger.info(f"API响应状态码: {response.status_code}")
        print(f"API响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info("API请求成功")
            print("API请求成功")
            
            if 'data' in data:
                answers = data['data']
                logger.info(f"获取到 {len(answers)} 个答案")
                print(f"获取到 {len(answers)} 个答案")
                
                # 保存响应数据
                with open('api_response_sample.json', 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                logger.info("响应数据已保存到 api_response_sample.json")
                print("响应数据已保存到 api_response_sample.json")
                
                # 打印响应数据
                print("\n=== API响应数据 ===")
                print(json.dumps(data, ensure_ascii=False, indent=2))
                
                return True
            else:
                logger.warning("API返回数据格式不正确")
                print("API返回数据格式不正确")
                print("\n=== API响应数据 ===")
                print(json.dumps(response.json(), ensure_ascii=False, indent=2))
                return False
        else:
            logger.error(f"API请求失败: {response.status_code}")
            print(f"API请求失败: {response.status_code}")
            print(f"响应内容: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"API连接测试失败: {e}")
        print(f"API连接测试失败: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def main():
    # 设置日志
    logger.add("logs/api_cookies_check.log", rotation="10 MB", level="INFO")
    
    # 加载cookies
    cookies_path = "cookies/zhihu_cookies.json"
    cookies_dict = load_cookies(cookies_path)
    
    # 无论是否加载到cookies，都尝试测试API连接
    # 因为我们已经在headers中直接设置了cookie
    print("\n=== 使用直接设置的cookie测试API连接 ===\n")
    test_api_connection(cookies_dict)
    
    if not cookies_dict:
        logger.warning("未加载cookies文件，但仍使用headers中的cookie进行测试")
        print("未加载cookies文件，但仍使用headers中的cookie进行测试")

if __name__ == "__main__":
    main()