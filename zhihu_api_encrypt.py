#!/usr/bin/env python3
"""
知乎API加密模块
用于生成知乎API请求所需的加密参数
"""

import hashlib
import hmac
import json
import time
import base64
from urllib.parse import urlencode
from loguru import logger


def get_x_zse_96(url, d_c0=None):
    """
    生成知乎API请求所需的x-zse-96参数
    参考：https://github.com/zkl2333/MR-extension/blob/master/src/utils/zhihu.js
    
    :param url: 请求的URL（不含域名）
    :param d_c0: d_c0 cookie值
    :return: x-zse-96参数值
    """
    try:
        # 固定的x-zse-93值
        x_zse_93 = "101_3_2.0"
        
        # 获取当前时间戳
        timestamp = str(int(time.time() * 1000))
        
        # 构建加密字符串
        # 格式：{x_zse_93}+{url}+{d_c0}
        encrypt_str = f"{x_zse_93}+{url}"
        if d_c0:
            encrypt_str += f"+{d_c0}"
        
        # MD5加密
        md5 = hashlib.md5(encrypt_str.encode('utf-8')).hexdigest()
        
        # 生成x-zse-96
        x_zse_96 = f"2.0_{md5}"
        
        return x_zse_96
    except Exception as e:
        logger.error(f"生成x-zse-96参数失败: {e}")
        return None


def get_api_headers(url, d_c0=None, x_zst_81=None):
    """
    获取知乎API请求所需的headers
    
    :param url: 请求的URL（不含域名）
    :param d_c0: d_c0 cookie值
    :param x_zst_81: x-zst-81 cookie值
    :return: headers字典
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Accept-Language': 'en,zh-CN;q=0.9,zh;q=0.8,de;q=0.7,zh-TW;q=0.6',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Connection': 'keep-alive',
        'Referer': 'https://www.zhihu.com/',
        'Sec-Ch-Ua': '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"macOS"',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'X-Requested-With': 'fetch',
        'X-Zse-93': '101_3_2.0',
    }
    
    # 添加x-zse-96
    x_zse_96 = get_x_zse_96(url, d_c0)
    if x_zse_96:
        headers['X-Zse-96'] = x_zse_96
    
    # 添加x-zst-81（如果有）
    if x_zst_81:
        headers['X-Zst-81'] = x_zst_81
    
    return headers


def extract_d_c0_from_cookies(cookies_dict):
    """
    从cookies字典中提取d_c0值
    
    :param cookies_dict: cookies字典
    :return: d_c0值或None
    """
    if not cookies_dict:
        return None
    
    # 尝试直接获取d_c0
    d_c0 = cookies_dict.get('d_c0')
    if d_c0:
        return d_c0
    
    # 如果cookies是列表形式，遍历查找
    if isinstance(cookies_dict, list):
        for cookie in cookies_dict:
            if isinstance(cookie, dict) and cookie.get('name') == 'd_c0':
                return cookie.get('value')
    
    return None


def build_zhihu_api_url(base_url, params=None):
    """
    构建知乎API URL
    
    :param base_url: 基础URL
    :param params: 参数字典
    :return: 完整URL
    """
    if not params:
        return base_url
    
    # 添加session_id（使用时间戳生成）
    if 'session_id' not in params:
        params['session_id'] = str(int(time.time() * 1000000))
    
    # 手动构建URL以避免编码问题
    param_str = urlencode(params)
    return f"{base_url}?{param_str}"


def test_api_encryption():
    """
    测试API加密功能
    """
    test_url = "/api/v4/questions/25038841/answers"
    test_d_c0 = "LhdUv57jkBqPTiH9tVCnp2xbGKAlvES8sWA=|1749179944"
    
    x_zse_96 = get_x_zse_96(test_url, test_d_c0)
    print(f"生成的x-zse-96: {x_zse_96}")
    
    headers = get_api_headers(test_url, test_d_c0)
    print(f"生成的headers: {json.dumps(headers, indent=2)}")


if __name__ == "__main__":
    test_api_encryption()