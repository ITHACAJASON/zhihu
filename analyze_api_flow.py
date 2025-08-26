#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析知乎API请求流程
检查是否需要先访问问题页面才能获取feeds数据
"""

import json
import requests
from zhihu_api_crawler import ZhihuAPIAnswerCrawler

def analyze_question_page():
    """分析问题页面，查看是否有API相关信息"""
    question_url = "https://www.zhihu.com/question/354793553"

    # 使用完整的cookies
    cookies = {
        'z_c0': '2|1:0|10:1755075132|4:z_c0|80:MS4xd3VNQUFBQUFBQUFtQUFBQVlBSlZUYXV0Zkdsbm50TGVYWmhvOG5yenlmNF9YR3pScXJod0NBPT0=|8da7ea89a4932bd80a737e1764568c8f7b4d0a1b5dc2afcfc34602e96abbfc40',
        'd_c0': 'LhdUv57jkBqPTiH9tVCnp2xbGKAlvES8sWA=|1749179944',
        '_xsrf': '3flFJjridUWXsRGeJD7cdpXEdWag6jkQ',
        'q_c1': '56361d2b4a2f4fe9b798e456f80f6469|1754226619000|1754226619000',
        '_zap': '50caaf95-3ccf-4c5a-88b9-009aacf2b626',
        'HMACCOUNT': 'F9EB196AA549EE10',
        'SESSIONID': '6weJp7oOsUphljzUPyigYeLsYe1RiSeklskebB6BhoN',
        'tst': 'r',
        'BEC': '6c53268835aec2199978cd4b4f988f8c',
        'edu_user_uuid': 'edu-v1|9f7f4490-118a-42c5-a431-0790e813acf6',
        '__zse_ck': '004_SfbW3Ksv154NLmOVohUo0f7=mH7yErOIBjvhyVKg/G2XBlR=1F9GdLNKCsmCxg/k0WAhkAsASggTaKW23rlsAZ2HtRhbER1uEGxhWq8eOpH2NI9aeJXONWSrhJzcCtNb-swracgijNx8rDHpO9JL3PgP/4R7ytSgvpOQRb0K0nX0AzAQ4wSGkSpo7D3LWZ4r943jmj9GFrhvl1aLVmdwuc//9i9SBynqd1dCVw4nZ6g4ITpbmYdBee4BPJqrvOH2j',
        'JOID': 'UVodB0_RRfyM6DCZQsxW44wr-yxT5jiVxp8G_AGlEYbohF3iHZ5gXOPuO59OpSfOUGqeedRLlmJOQQksifNhNA0=',
        'osd': 'Ul8RAk_SQPCJ6DOcTslW4Ikn_ixQ4zSQxpwD8ASlEoPkgV3hGJJlXODrN5pOpiLCVWqdfNhOlmFLTQwsivZtMQ0=',
        'Hm_lvt_98beee57fd2ef70ccdd5ca52b9740c49': '1754226603',
        'Hm_lpvt_98beee57fd2ef70ccdd5ca52b9740c49': '1756124535'
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en,zh-CN;q=0.9,zh;q=0.8,de;q=0.7,zh-TW;q=0.6',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0'
    }

    print("=== 分析问题页面 ===")

    try:
        # 创建会话以保持cookies
        session = requests.Session()
        session.cookies.update(cookies)

        response = session.get(question_url, headers=headers, timeout=30)
        print(f"问题页面状态码: {response.status_code}")
        print(f"响应长度: {len(response.text)}")

        if response.status_code == 200:
            page_content = response.text

            # 查找API相关信息
            api_indicators = [
                'feeds',
                'api/v4/questions',
                'session',
                'cursor',
                'data',
                'target',
                'answer'
            ]

            print("\n=== 页面中API相关信息分析 ===")
            for indicator in api_indicators:
                count = page_content.count(indicator)
                if count > 0:
                    print(f"✓ 找到 '{indicator}': {count} 次")

            # 查找preload信息
            if 'preload' in page_content:
                print("\n=== 找到preload信息 ===")
                # 提取preload部分
                start = page_content.find('preload')
                if start != -1:
                    # 查找JSON开始
                    json_start = page_content.find('{', start)
                    if json_start != -1:
                        # 简单提取JSON（这只是近似，可能需要更精确的解析）
                        json_end = page_content.find('</script>', json_start)
                        if json_end != -1:
                            preload_json = page_content[json_start:json_end]
                            print("Preload JSON (前500字符):")
                            print(preload_json[:500] + "...")

            # 检查是否有答案相关信息
            answer_indicators = [
                '回答',
                'answer',
                'answers',
                '写回答',
                '添加回答'
            ]

            print("\n=== 页面答案相关信息 ===")
            for indicator in answer_indicators:
                count = page_content.count(indicator)
                if count > 0:
                    print(f"✓ 找到 '{indicator}': {count} 次")

            # 保存页面内容用于进一步分析
            with open('question_page_full.html', 'w', encoding='utf-8') as f:
                f.write(page_content)
            print("\n✓ 完整页面内容已保存到 question_page_full.html")

        else:
            print(f"✗ 页面访问失败: {response.status_code}")

    except Exception as e:
        print(f"访问失败: {e}")
        import traceback
        traceback.print_exc()

def analyze_api_flow():
    """分析API请求流程"""
    print("\n=== 分析API请求流程 ===")

    # 测试直接API调用
    print("1. 直接API调用测试...")
    crawler = ZhihuAPIAnswerCrawler()

    # 先测试连接
    if not crawler.test_api_connection():
        print("✗ API连接测试失败")
        return

    # 测试feeds API
    print("\n2. Feeds API调用分析...")
    question_id = "354793553"

    # 手动构建请求
    api_url = f"https://www.zhihu.com/api/v4/questions/{question_id}/feeds"
    params = {
        'include': 'data[*].is_normal,admin_closed_comment,reward_info,is_collapsed,annotation_action,annotation_detail,collapse_reason,is_sticky,collapsed_by,suggest_edit,comment_count,can_comment,content,editable_content,attachment,voteup_count,reshipment_settings,comment_permission,created_time,updated_time,review_info,relevant_info,question,excerpt,is_labeled,paid_info,paid_info_content,reaction_instruction,relationship.is_authorized,is_author,voting,is_thanked,is_nothelp;data[*].author.follower_count,vip_info,kvip_info,badge[*].topics;data[*].settings.table_of_content.enabled',
        'offset': '',
        'limit': '3',
        'order': 'default',
        'ws_qiangzhisafe': '0',
        'platform': 'desktop',
        'session_id': ''
    }

    headers = crawler.headers.copy()
    headers['Referer'] = f'https://www.zhihu.com/question/{question_id}'

    print(f"API URL: {api_url}")
    print(f"参数: {json.dumps(params, indent=2, ensure_ascii=False)}")

    try:
        response = crawler.session.get(api_url, params=params, headers=headers, timeout=30)
        print(f"\nAPI响应状态: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            print("\n响应分析:")
            print(f"  - data数组长度: {len(data.get('data', []))}")
            print(f"  - session.id: '{data.get('session', {}).get('id', '')}'")
            print(f"  - paging.is_end: {data.get('paging', {}).get('is_end', 'N/A')}")

            if data.get('data'):
                first_item = data['data'][0]
                print(f"  - 第一项类型: {first_item.get('target_type', 'N/A')}")
                if 'target' in first_item:
                    target = first_item['target']
                    print(f"  - target.id: {target.get('id', 'N/A')}")
                    print(f"  - target类型: {type(target)}")

            # 保存详细响应
            with open('detailed_api_response.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("✓ 详细API响应已保存到 detailed_api_response.json")

        else:
            print(f"API请求失败: {response.status_code}")
            print(f"响应内容: {response.text}")

    except Exception as e:
        print(f"API调用异常: {e}")
        import traceback
        traceback.print_exc()

def check_question_info():
    """检查问题基本信息"""
    print("\n=== 检查问题基本信息 ===")

    question_id = "354793553"
    api_url = f"https://www.zhihu.com/api/v4/questions/{question_id}"

    crawler = ZhihuAPIAnswerCrawler()

    params = {
        'include': 'answer_count,author,detail,excerpt,follower_count,title,created,updated_time,question_type,relationship',
        'limit': '0'
    }

    try:
        response = crawler.session.get(api_url, params=params, headers=crawler.headers, timeout=30)
        print(f"问题信息API状态: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"问题标题: {data.get('title', 'N/A')}")
            print(f"回答数量: {data.get('answer_count', 'N/A')}")
            print(f"关注者数量: {data.get('follower_count', 'N/A')}")
            print(f"问题状态: {data.get('question_type', 'N/A')}")

            # 保存问题信息
            with open('question_info.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("✓ 问题信息已保存到 question_info.json")

        else:
            print(f"获取问题信息失败: {response.status_code}")

    except Exception as e:
        print(f"获取问题信息异常: {e}")

if __name__ == "__main__":
    analyze_question_page()
    analyze_api_flow()
    check_question_info()
