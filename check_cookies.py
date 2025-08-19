#!/usr/bin/env python3
"""
检查cookies有效性
"""

import json
from datetime import datetime
from loguru import logger

def check_cookies():
    """检查cookies有效性"""
    try:
        with open('./cookies/zhihu_cookies.json', 'r', encoding='utf-8') as f:
            cookies = json.load(f)
        
        current_time = datetime.now().timestamp()
        logger.info(f"当前时间戳: {current_time}")
        logger.info(f"当前时间: {datetime.fromtimestamp(current_time)}")
        
        expired_cookies = []
        valid_cookies = []
        
        for cookie in cookies:
            name = cookie.get('name', 'unknown')
            expiry = cookie.get('expiry')
            
            if expiry:
                expiry_time = datetime.fromtimestamp(expiry)
                if expiry < current_time:
                    expired_cookies.append({
                        'name': name,
                        'expiry': expiry_time,
                        'expired_days': (current_time - expiry) / 86400
                    })
                else:
                    valid_cookies.append({
                        'name': name,
                        'expiry': expiry_time,
                        'remaining_days': (expiry - current_time) / 86400
                    })
            else:
                # 没有过期时间的cookie（会话cookie）
                valid_cookies.append({
                    'name': name,
                    'expiry': 'Session',
                    'remaining_days': 'N/A'
                })
        
        logger.info(f"\n{'='*50}")
        logger.info("Cookie有效性检查结果:")
        
        if expired_cookies:
            logger.error(f"发现 {len(expired_cookies)} 个过期的cookies:")
            for cookie in expired_cookies:
                logger.error(f"  - {cookie['name']}: 过期时间 {cookie['expiry']}, 已过期 {cookie['expired_days']:.1f} 天")
        else:
            logger.info("没有发现过期的cookies")
        
        if valid_cookies:
            logger.info(f"\n有效的cookies ({len(valid_cookies)} 个):")
            for cookie in valid_cookies:
                if cookie['remaining_days'] == 'N/A':
                    logger.info(f"  - {cookie['name']}: 会话cookie")
                else:
                    logger.info(f"  - {cookie['name']}: 过期时间 {cookie['expiry']}, 剩余 {cookie['remaining_days']:.1f} 天")
        
        # 检查关键cookies
        key_cookies = ['z_c0', 'q_c1', 'BEC']
        missing_key_cookies = []
        
        cookie_names = [cookie.get('name') for cookie in cookies]
        for key_cookie in key_cookies:
            if key_cookie not in cookie_names:
                missing_key_cookies.append(key_cookie)
        
        if missing_key_cookies:
            logger.error(f"\n缺少关键cookies: {missing_key_cookies}")
        else:
            logger.info("\n所有关键cookies都存在")
        
        # 检查z_c0 cookie的值
        z_c0_cookie = next((cookie for cookie in cookies if cookie.get('name') == 'z_c0'), None)
        if z_c0_cookie:
            z_c0_value = z_c0_cookie.get('value', '')
            logger.info(f"\nz_c0 cookie长度: {len(z_c0_value)}")
            if len(z_c0_value) < 100:
                logger.warning("z_c0 cookie值可能异常（长度过短）")
            else:
                logger.info("z_c0 cookie值长度正常")
        
        return len(expired_cookies) == 0
        
    except Exception as e:
        logger.error(f"检查cookies失败: {e}")
        return False

if __name__ == '__main__':
    check_cookies()