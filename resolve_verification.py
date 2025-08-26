#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解决知乎验证问题的工具
"""

import webbrowser
import json
import time
from loguru import logger

def open_verification_page():
    """打开验证页面"""
    verification_url = "https://www.zhihu.com/account/unhuman?type=Q8J2L3&need_login=false&session=09e67be5ec2c64778adaa69652785962"
    
    logger.info("🌐 正在打开知乎验证页面...")
    logger.info(f"📱 验证URL: {verification_url}")
    
    # 在默认浏览器中打开验证页面
    webbrowser.open(verification_url)
    
    print("\n" + "="*60)
    print("🔧 解决知乎验证问题 - 操作指南")
    print("="*60)
    print("1. 浏览器将自动打开知乎验证页面")
    print("2. 请在页面中完成验证（点击、滑动等）")
    print("3. 验证成功后，等待页面跳转")
    print("4. 跳转成功后，回到这里按 Enter 继续")
    print("="*60)
    
    input("\n✅ 完成验证后，按 Enter 键继续...")
    
    return True

def test_after_verification():
    """验证完成后测试API"""
    try:
        from zhihu_api_fix import ZhihuAPIFixer
        
        logger.info("🔍 验证后测试API状态...")
        
        fixer = ZhihuAPIFixer()
        
        # 检查登录状态
        if fixer.check_login_status():
            logger.info("✅ 登录状态正常")
        else:
            logger.warning("❌ 登录状态异常")
            return False
        
        # 测试一个简单的API
        question_id = "354793553"
        basic_info = fixer.get_question_basic_info(question_id)
        
        if basic_info:
            logger.info(f"✅ API测试成功！")
            logger.info(f"📝 问题标题: {basic_info.get('title', 'Unknown')}")
            logger.info(f"💬 答案数量: {basic_info.get('answer_count', 0)}")
            return True
        else:
            logger.warning("❌ API仍然无法访问")
            return False
            
    except Exception as e:
        logger.error(f"测试失败: {e}")
        return False

def main():
    """主函数"""
    print("🚀 知乎API验证问题解决工具")
    print("=" * 50)
    
    # 打开验证页面
    open_verification_page()
    
    # 验证后测试
    if test_after_verification():
        print("\n🎉 恭喜！验证成功，API现在应该可以正常工作了")
        print("\n📋 建议:")
        print("1. 立即运行您的爬虫程序")
        print("2. 避免过于频繁的请求")
        print("3. 添加合理的延时机制")
    else:
        print("\n⚠️ 验证可能未完全生效，请:")
        print("1. 确认验证页面显示成功")
        print("2. 等待几分钟后重试")
        print("3. 如果问题持续，可能需要更换网络环境")

if __name__ == "__main__":
    main()

